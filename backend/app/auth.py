import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db
from app.database.models import OAuthAccount, OAuthState, User, UserSession

password_hash = PasswordHash.recommended()
SESSION_COOKIE = settings.SESSION_COOKIE_NAME
OAUTH_STATE_TTL = timedelta(minutes=10)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _csrf_token(session_token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _set_session_cookie(response: Response, db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=settings.SESSION_TTL_HOURS)
    db.add(UserSession(user_id=user.id, token_hash=_hash_token(token), expires_at=expires_at))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.SESSION_TTL_HOURS * 3600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )
    return token


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connexion requise.")
    session = (
        db.query(UserSession)
        .filter(
            UserSession.token_hash == _hash_token(token),
            UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée.")
    return session.user


def require_csrf(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    token = request.cookies.get(SESSION_COOKIE, "")
    supplied = request.headers.get("x-csrf-token", "")
    expected = _csrf_token(token)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Jeton CSRF invalide.")
    return user


def current_user_payload(
    request: Request,
    user: User,
    session_token: str | None = None,
) -> dict[str, Any]:
    session_token = session_token or request.cookies.get(SESSION_COOKIE, "")
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "csrf_token": _csrf_token(session_token),
    }


def _new_session_redirect(db: Session, user: User, url: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, db, user)
    return response


def _oauth_config(provider: str) -> tuple[str, str, str]:
    if provider == "google":
        return (
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            "https://accounts.google.com/o/oauth2/v2/auth",
        )
    if provider == "github":
        return (
            settings.GITHUB_CLIENT_ID,
            settings.GITHUB_CLIENT_SECRET,
            "https://github.com/login/oauth/authorize",
        )
    raise HTTPException(status_code=404, detail="Fournisseur OAuth inconnu.")


def _callback_url(provider: str, request: Request) -> str:
    base_url = settings.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    return f"{base_url}/api/auth/{provider}/callback"


async def start_oauth(provider: str, request: Request, db: Session) -> RedirectResponse:
    client_id, client_secret, authorization_endpoint = _oauth_config(provider)
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail=f"Connexion {provider} non configurée.")

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at <= now).delete()
    db.add(OAuthState(
        state_hash=_hash_token(state),
        provider=provider,
        code_verifier=verifier,
        expires_at=now + OAUTH_STATE_TTL,
    ))
    db.commit()

    parameters = {
        "client_id": client_id,
        "redirect_uri": _callback_url(provider, request),
        "response_type": "code",
        "scope": "openid email profile" if provider == "google" else "read:user user:email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if provider == "google":
        parameters["prompt"] = "select_account"

    response = RedirectResponse(
        f"{authorization_endpoint}?{urlencode(parameters)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        f"oauth_state_{provider}",
        state,
        max_age=int(OAUTH_STATE_TTL.total_seconds()),
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path=f"/api/auth/{provider}/callback",
    )
    return response


async def _exchange_code(
    provider: str,
    code: str,
    verifier: str,
    callback_url: str,
) -> tuple[str, str, str]:
    client_id, client_secret, _ = _oauth_config(provider)
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token" if provider == "google"
            else "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": callback_url,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ValueError("Le fournisseur n'a pas retourné de jeton OAuth.")

        if provider == "google":
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
            if profile.get("email_verified") is not True:
                raise ValueError("L'adresse Google n'est pas vérifiée.")
            email = profile.get("email")
            subject = profile.get("sub")
            name = profile.get("name") or ""
        else:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            profile_response = await client.get("https://api.github.com/user", headers=headers)
            profile_response.raise_for_status()
            profile = profile_response.json()
            email_response = await client.get("https://api.github.com/user/emails", headers=headers)
            email_response.raise_for_status()
            verified_emails = [
                item for item in email_response.json()
                if item.get("verified") and item.get("primary")
            ]
            email = verified_emails[0].get("email") if verified_emails else None
            subject = str(profile.get("id") or "")
            name = profile.get("name") or profile.get("login") or ""

    if not isinstance(email, str) or not isinstance(subject, str) or not subject:
        raise ValueError("Le fournisseur n'a pas fourni une identité vérifiée.")
    return email.strip().lower(), subject, name[:120]


async def finish_oauth(
    provider: str,
    request: Request,
    db: Session,
    code: str | None,
    state: str | None,
    error: str | None,
) -> RedirectResponse:
    frontend = settings.FRONTEND_ORIGIN
    cookie_name = f"oauth_state_{provider}"
    cookie_state = request.cookies.get(cookie_name)
    state_record = None
    if state and cookie_state and hmac.compare_digest(state, cookie_state):
        state_record = db.query(OAuthState).filter(
            OAuthState.state_hash == _hash_token(state),
            OAuthState.provider == provider,
            OAuthState.expires_at > datetime.utcnow(),
        ).first()

    if state_record is None:
        raise HTTPException(status_code=400, detail="État OAuth invalide, expiré ou refusé.")

    verifier = state_record.code_verifier
    db.delete(state_record)
    db.commit()
    if error or not code:
        response = RedirectResponse(f"{frontend}/?auth_error=oauth_failed", status_code=303)
        response.delete_cookie(cookie_name, path=f"/api/auth/{provider}/callback")
        return response
    try:
        email, subject, display_name = await _exchange_code(
            provider, code, verifier, _callback_url(provider, request)
        )
    except (httpx.HTTPError, ValueError):
        response = RedirectResponse(f"{frontend}/?auth_error=oauth_failed", status_code=303)
        response.delete_cookie(cookie_name, path=f"/api/auth/{provider}/callback")
        return response

    account = db.query(OAuthAccount).filter_by(
        provider=provider, provider_user_id=subject
    ).first()
    if account:
        user = account.user
    else:
        user = db.query(User).filter_by(email=email).first()
        if user is None:
            user = User(email=email, display_name=display_name or None)
            db.add(user)
            db.flush()
        db.add(OAuthAccount(user_id=user.id, provider=provider, provider_user_id=subject))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            account = db.query(OAuthAccount).filter_by(
                provider=provider, provider_user_id=subject
            ).first()
            if account is None:
                response = RedirectResponse(f"{frontend}/?auth_error=oauth_failed", status_code=303)
                response.delete_cookie(cookie_name, path=f"/api/auth/{provider}/callback")
                return response
            user = account.user

    response = _new_session_redirect(db, user, frontend)
    response.delete_cookie(cookie_name, path=f"/api/auth/{provider}/callback")
    return response

import React, { FormEvent, useEffect, useState } from 'react';
import { Shield } from 'lucide-react';
import {
  AuthUser,
  getAuthProviders,
  loginAccount,
  registerAccount,
  setCsrfToken,
} from '../api/client';
import { Language } from '../i18n/translations';

interface AuthScreenProps {
  lang: Language;
  onAuthenticated: (user: AuthUser) => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ lang, onAuthenticated }) => {
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [providers, setProviders] = useState({ google: false, github: false });
  const isFrench = lang === 'fr';
  const authError = new URLSearchParams(window.location.search).get('auth_error');

  useEffect(() => {
    getAuthProviders().then(setProviders).catch(() => setProviders({ google: false, github: false }));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const user = isRegistering
        ? await registerAccount(email, password, displayName)
        : await loginAccount(email, password);
      setCsrfToken(user.csrf_token);
      window.history.replaceState({}, '', window.location.pathname);
      onAuthenticated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand">
          <Shield size={32} />
          <span>X-Finder</span>
        </div>
        <h1>{isRegistering
          ? (isFrench ? 'Créer votre compte' : 'Create your account')
          : (isFrench ? 'Content de vous revoir' : 'Welcome back')}</h1>
        <p className="auth-description">
          {isFrench
            ? 'Connectez-vous pour retrouver vos missions et utiliser votre agent.'
            : 'Sign in to access your missions and use your agent.'}
        </p>

        {authError && (
          <p className="auth-error">
            {isFrench
              ? 'La connexion avec le fournisseur a échoué. Réessayez.'
              : 'Provider sign-in failed. Please try again.'}
          </p>
        )}

        {(providers.google || providers.github) && (
          <div className="auth-oauth-actions">
            {providers.google && (
              <a href="/api/auth/google/login" className="auth-provider-button">
                {isFrench ? 'Continuer avec Google' : 'Continue with Google'}
              </a>
            )}
            {providers.github && (
              <a href="/api/auth/github/login" className="auth-provider-button">
                {isFrench ? 'Continuer avec GitHub' : 'Continue with GitHub'}
              </a>
            )}
          </div>
        )}

        {(providers.google || providers.github) && (
          <div className="auth-divider"><span>{isFrench ? 'ou par email' : 'or with email'}</span></div>
        )}

        <form className="auth-form" onSubmit={submit}>
          {isRegistering && (
            <label>
              {isFrench ? 'Nom (facultatif)' : 'Name (optional)'}
              <input
                autoComplete="name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                maxLength={120}
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            {isFrench ? 'Mot de passe' : 'Password'}
            <input
              type="password"
              autoComplete={isRegistering ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={isRegistering ? 12 : undefined}
              maxLength={128}
              required
            />
            {isRegistering && (
              <small>{isFrench ? '12 caractères minimum.' : 'At least 12 characters.'}</small>
            )}
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button className="auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? (isFrench ? 'Veuillez patienter…' : 'Please wait…')
              : isRegistering
                ? (isFrench ? 'Créer le compte' : 'Create account')
                : (isFrench ? 'Se connecter' : 'Sign in')}
          </button>
        </form>

        <button
          type="button"
          className="auth-mode-toggle"
          onClick={() => {
            setError('');
            setIsRegistering(!isRegistering);
          }}
        >
          {isRegistering
            ? (isFrench ? 'Déjà un compte ? Se connecter' : 'Already registered? Sign in')
            : (isFrench ? 'Nouveau ici ? Créer un compte' : 'New here? Create an account')}
        </button>
      </section>
    </main>
  );
};

import React, { FormEvent, useEffect, useState } from 'react';
import { LogOut, Save, UserRound } from 'lucide-react';
import { AuthUser, updateProfile } from '../api/client';
import { Language } from '../i18n/translations';

interface ProfileMenuProps {
  user: AuthUser;
  lang: Language;
  onUpdated: (user: AuthUser) => void;
  onLogout: () => void;
}

export const ProfileMenu: React.FC<ProfileMenuProps> = ({
  user,
  lang,
  onUpdated,
  onLogout,
}) => {
  const [displayName, setDisplayName] = useState(user.display_name || '');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const isFrench = lang === 'fr';
  const label = user.display_name?.trim() || user.email.split('@')[0];
  const initials = label.slice(0, 1).toUpperCase();

  useEffect(() => {
    setDisplayName(user.display_name || '');
  }, [user.display_name]);

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setIsSaving(true);
    try {
      onUpdated(await updateProfile(displayName));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <details className="profile-menu">
      <summary className="profile-trigger" aria-label={isFrench ? 'Ouvrir le profil' : 'Open profile'}>
        <span className="profile-avatar">{initials || <UserRound size={16} />}</span>
        <span className="profile-trigger-name">{label}</span>
      </summary>
      <section className="profile-panel" aria-label={isFrench ? 'Profil utilisateur' : 'User profile'}>
        <div className="profile-panel-heading">
          <strong>{isFrench ? 'Mon profil' : 'My profile'}</strong>
          <span>{user.email}</span>
        </div>
        <form className="profile-form" onSubmit={saveProfile}>
          <label htmlFor="profile-display-name">{isFrench ? 'Nom affiché' : 'Display name'}</label>
          <input
            id="profile-display-name"
            autoComplete="name"
            maxLength={120}
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
          {error && <p className="profile-error" role="alert">{error}</p>}
          <button className="profile-action profile-save" type="submit" disabled={isSaving}>
            <Save size={15} />
            {isSaving
              ? (isFrench ? 'Enregistrement…' : 'Saving…')
              : (isFrench ? 'Enregistrer' : 'Save changes')}
          </button>
        </form>
        <button className="profile-action profile-logout" type="button" onClick={onLogout}>
          <LogOut size={15} />
          {isFrench ? 'Déconnexion' : 'Sign out'}
        </button>
      </section>
    </details>
  );
};

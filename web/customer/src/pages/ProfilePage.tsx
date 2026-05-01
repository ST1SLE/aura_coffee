import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Languages, LogOut, MapPin, Phone, UserRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/auth/useAuth';
import { getProfile, updateProfile, type ProfileData } from '@/api/profile';
import { LoyaltyCard } from '@/pages/Profile/LoyaltyCard';

// START_MODULE_CONTRACT
//   PURPOSE: /profile route — show masked phone, edit display name, switch
//            preferred language (also calls i18n.changeLanguage so the UI
//            updates immediately), navigate to addresses, render LoyaltyCard,
//            and provide the logout button.
//   SCOPE:   ProfilePage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/components/ui/button,
//            @/auth/useAuth, @/api/profile (getProfile, updateProfile),
//            @/pages/Profile/LoyaltyCard.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §8 profile;
//            INV-013 — display_name + phone are PII; phone is shown masked.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ProfilePage  - /profile — name/language editor + addresses link + logout
// END_MODULE_MAP

// START_CONTRACT: ProfilePage
//   PURPOSE: Render the profile editor and bind it to the profile API.
//   INPUTS:  none.
//   OUTPUTS: JSX — phone (read-only) / name editor / language toggle /
//            addresses link / LoyaltyCard / logout button.
//   SIDE_EFFECTS: HTTP getProfile() on mount; updateProfile() on save / lang
//                 toggle (and calls i18n.changeLanguage for client-side UI);
//                 useAuth().logout() then navigate('/login') from the logout
//                 button. INV-013 — do not log raw display_name / phone.
//   LINKS:   PDD §8; AGENTS.md "must not store auth tokens in localStorage" —
//            access token is in-memory; logout clears both.
// END_CONTRACT: ProfilePage
export function ProfilePage() {
  const { t, i18n } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProfile();
      setProfile(data);
      setDisplayName(data.display_name ?? '');
    } catch {
      setError(t('pages.profile.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void fetchProfile();
  }, [fetchProfile]);

  const handleSaveName = async () => {
    if (!displayName.trim()) {
      setNameError(t('pages.profile.nameRequired'));
      return;
    }
    if (displayName.length > 100) {
      setNameError(t('pages.profile.nameTooLong'));
      return;
    }
    setNameError(null);
    setSaving(true);
    try {
      const updated = await updateProfile({ display_name: displayName });
      setProfile(updated);
    } catch {
      setNameError(t('pages.profile.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleLanguageChange = async (lang: 'ru' | 'en') => {
    setSaving(true);
    try {
      const updated = await updateProfile({ preferred_language: lang });
      setProfile(updated);
      await i18n.changeLanguage(lang);
    } catch {
      setError(t('pages.profile.saveError'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground" />
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-4 text-center">
        <p className="text-destructive">{error}</p>
        <Button className="mt-4" onClick={fetchProfile}>
          {t('pages.profile.retry')}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-4 py-5 md:px-6">
      <div className="aura-surface rounded-lg p-4">
        <h1 className="text-3xl font-semibold tracking-normal">
          {t('pages.profile.title')}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t('pages.profile.description')}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="aura-surface rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Phone className="h-4 w-4 text-primary" aria-hidden="true" />
            <label>{t('pages.profile.phoneLabel')}</label>
          </div>
          <p className="rounded-md border border-white/10 bg-background/75 px-3 py-2 text-sm">
            {profile?.phone_masked}
          </p>
        </div>

        <div className="aura-surface rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Languages className="h-4 w-4 text-primary" aria-hidden="true" />
            <label>{t('pages.profile.languageLabel')}</label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant={
                profile?.preferred_language === 'ru' ? 'default' : 'outline'
              }
              onClick={() => handleLanguageChange('ru')}
              disabled={saving || profile?.preferred_language === 'ru'}
            >
              Русский
            </Button>
            <Button
              variant={
                profile?.preferred_language === 'en' ? 'default' : 'outline'
              }
              onClick={() => handleLanguageChange('en')}
              disabled={saving || profile?.preferred_language === 'en'}
            >
              English
            </Button>
          </div>
        </div>
      </div>

      <div className="aura-surface rounded-lg p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <UserRound className="h-4 w-4 text-primary" aria-hidden="true" />
          <label>{t('pages.profile.nameLabel')}</label>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setNameError(null);
            }}
            maxLength={100}
            className="min-w-0 flex-1 rounded-md border border-white/10 bg-background/75 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button
            onClick={handleSaveName}
            disabled={saving || displayName === (profile?.display_name ?? '')}
          >
            {t('pages.profile.save')}
          </Button>
        </div>
        {nameError && (
          <p className="mt-2 text-sm text-destructive">{nameError}</p>
        )}
      </div>

      <Link
        to="/profile/addresses"
        className="aura-surface flex items-center gap-3 rounded-lg p-4 transition-colors hover:bg-accent"
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-secondary text-primary">
          <MapPin className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <div className="text-sm font-medium">
            {t('pages.profile.addressesLink.title')}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t('pages.profile.addressesLink.subtitle')}
          </div>
        </div>
      </Link>

      {error && profile && <p className="text-sm text-destructive">{error}</p>}

      <LoyaltyCard />

      {/* Выход */}
      <Button
        variant="outline"
        className="w-full text-destructive"
        onClick={async () => {
          await logout();
          navigate('/login');
        }}
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        {t('pages.profile.logout')}
      </Button>
    </div>
  );
}

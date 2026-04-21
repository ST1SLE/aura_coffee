import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/auth/useAuth';
import {
  getProfile,
  updateProfile,
  type ProfileData,
} from '@/api/profile';
import { LoyaltyCard } from '@/pages/Profile/LoyaltyCard';

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

  const fetchProfile = async () => {
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
  };

  useEffect(() => {
    fetchProfile();
  }, []);

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
      <div className="mx-auto max-w-md py-12 text-center">
        <p className="text-destructive">{error}</p>
        <Button className="mt-4" onClick={fetchProfile}>
          {t('pages.profile.retry')}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <h1 className="text-2xl font-bold">{t('pages.profile.title')}</h1>

      {/* Телефон (только чтение) */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">
          {t('pages.profile.phoneLabel')}
        </label>
        <p className="mt-1 rounded-md border bg-muted px-3 py-2 text-sm">
          {profile?.phone_masked}
        </p>
      </div>

      {/* Имя */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">
          {t('pages.profile.nameLabel')}
        </label>
        <div className="mt-1 flex gap-2">
          <input
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setNameError(null);
            }}
            maxLength={100}
            className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button
            onClick={handleSaveName}
            disabled={saving || displayName === (profile?.display_name ?? '')}
          >
            {t('pages.profile.save')}
          </Button>
        </div>
        {nameError && <p className="mt-1 text-sm text-destructive">{nameError}</p>}
      </div>

      {/* Язык */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">
          {t('pages.profile.languageLabel')}
        </label>
        <div className="mt-1 flex gap-2">
          <Button
            variant={profile?.preferred_language === 'ru' ? 'default' : 'outline'}
            onClick={() => handleLanguageChange('ru')}
            disabled={saving || profile?.preferred_language === 'ru'}
          >
            Русский
          </Button>
          <Button
            variant={profile?.preferred_language === 'en' ? 'default' : 'outline'}
            onClick={() => handleLanguageChange('en')}
            disabled={saving || profile?.preferred_language === 'en'}
          >
            English
          </Button>
        </div>
      </div>

      <Link
        to="/profile/addresses"
        className="block rounded-md border p-4 hover:bg-accent"
      >
        <div className="text-sm font-medium">
          {t('pages.profile.addressesLink.title')}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {t('pages.profile.addressesLink.subtitle')}
        </div>
      </Link>

      {error && profile && (
        <p className="text-sm text-destructive">{error}</p>
      )}

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
        {t('pages.profile.logout')}
      </Button>
    </div>
  );
}

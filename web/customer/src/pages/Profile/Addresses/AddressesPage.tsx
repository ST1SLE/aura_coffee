import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Edit3, MapPin, Plus, Star, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  listAddresses,
  deleteAddress,
  setDefaultAddress,
  type AddressResponse,
} from '@/api/addresses';
import { AddressForm } from './AddressForm';

// START_MODULE_CONTRACT
//   PURPOSE: /profile/addresses route — list saved addresses, mark one default,
//            and switch into create/edit modes that mount AddressForm. Confirms
//            deletion via window.confirm before calling api/addresses.deleteAddress.
//   SCOPE:   AddressesPage component.
//   DEPENDS: react, react-i18next, @/components/ui/button, @/api/addresses
//            (listAddresses, deleteAddress, setDefaultAddress), ./AddressForm.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 saved addresses;
//            INV-013 PII handling.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AddressesPage  - /profile/addresses — list/create/edit mode switcher
// END_MODULE_MAP

type Mode =
  | { kind: 'list' }
  | { kind: 'create' }
  | { kind: 'edit'; address: AddressResponse };

// START_CONTRACT: AddressesPage
//   PURPOSE: Drive list/create/edit modes for saved delivery addresses.
//   INPUTS:  none.
//   OUTPUTS: JSX — loading spinner / list with action buttons / AddressForm.
//   SIDE_EFFECTS: HTTP listAddresses() on mount and after every mutation;
//                 deleteAddress() (confirm-gated); setDefaultAddress();
//                 mounting AddressForm triggers further HTTP calls.
//                 INV-013 PII handling.
//   LINKS:   PDD §7.
// END_CONTRACT: AddressesPage
export function AddressesPage() {
  const { t } = useTranslation();
  const [addresses, setAddresses] = useState<AddressResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>({ kind: 'list' });

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listAddresses();
      setAddresses(items);
    } catch {
      setError(t('pages.profile.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  async function handleDelete(id: string) {
    if (!confirm(t('pages.addresses.confirmDelete'))) return;
    try {
      await deleteAddress(id);
      await refetch();
    } catch {
      setError(t('pages.profile.saveError'));
    }
  }

  async function handleSetPrimary(id: string) {
    try {
      await setDefaultAddress(id);
      await refetch();
    } catch {
      setError(t('pages.profile.saveError'));
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 px-4 py-5 md:px-0">
      <div className="aura-surface flex flex-col gap-3 rounded-lg bg-card/95 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-primary/25 bg-primary text-primary-foreground">
            <MapPin className="h-5 w-5" aria-hidden="true" />
          </span>
          <h1 className="font-display text-2xl font-bold">
            {t('pages.addresses.title')}
          </h1>
        </div>
        {mode.kind === 'list' && (
          <Button
            size="sm"
            className="w-full sm:w-auto"
            onClick={() => setMode({ kind: 'create' })}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            {t('pages.addresses.addButton')}
          </Button>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {mode.kind === 'list' && (
        <>
          {addresses.length === 0 ? (
            <div className="aura-surface rounded-lg bg-card/95 p-4 text-sm text-muted-foreground">
              <p>{t('pages.addresses.empty')}</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {addresses.map((a) => (
                <li
                  key={a.id}
                  className="aura-surface rounded-lg bg-card/95 p-4 text-sm"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      {a.label && (
                        <div className="font-display text-base font-semibold">
                          {a.label}
                        </div>
                      )}
                      <div className="mt-1 break-words">{a.address_text}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {[
                          a.apartment && `кв. ${a.apartment}`,
                          a.entrance && `подъезд ${a.entrance}`,
                          a.floor && `этаж ${a.floor}`,
                        ]
                          .filter(Boolean)
                          .join(', ')}
                      </div>
                      {a.is_default && (
                        <span className="mt-3 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-display text-xs font-semibold text-primary">
                          <Star
                            className="h-3 w-3 fill-current"
                            aria-hidden="true"
                          />
                          {t('pages.addresses.primaryBadge')}
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:flex sm:min-w-36 sm:flex-col">
                      {!a.is_default && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSetPrimary(a.id)}
                          className="col-span-2 sm:col-span-1"
                        >
                          <Star className="h-4 w-4" aria-hidden="true" />
                          {t('pages.addresses.makePrimary')}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setMode({ kind: 'edit', address: a })}
                      >
                        <Edit3 className="h-4 w-4" aria-hidden="true" />
                        {t('pages.addresses.edit')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-destructive"
                        onClick={() => handleDelete(a.id)}
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                        {t('pages.addresses.delete')}
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {mode.kind === 'create' && (
        <AddressForm
          onSaved={async () => {
            setMode({ kind: 'list' });
            await refetch();
          }}
          onCancel={() => setMode({ kind: 'list' })}
        />
      )}

      {mode.kind === 'edit' && (
        <AddressForm
          initial={mode.address}
          onSaved={async () => {
            setMode({ kind: 'list' });
            await refetch();
          }}
          onCancel={() => setMode({ kind: 'list' })}
        />
      )}
    </div>
  );
}

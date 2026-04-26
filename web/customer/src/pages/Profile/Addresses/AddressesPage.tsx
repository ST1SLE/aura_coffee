import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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

  async function refetch() {
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
  }

  useEffect(() => {
    void refetch();
  }, []);

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
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-bold">{t('pages.addresses.title')}</h1>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {mode.kind === 'list' && (
        <>
          {addresses.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t('pages.addresses.empty')}
            </p>
          ) : (
            <ul className="space-y-3">
              {addresses.map((a) => (
                <li
                  key={a.id}
                  className="rounded-md border p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      {a.label && (
                        <div className="font-medium">{a.label}</div>
                      )}
                      <div>{a.address_text}</div>
                      <div className="text-xs text-muted-foreground">
                        {[
                          a.apartment && `кв. ${a.apartment}`,
                          a.entrance && `подъезд ${a.entrance}`,
                          a.floor && `этаж ${a.floor}`,
                        ]
                          .filter(Boolean)
                          .join(', ')}
                      </div>
                      {a.is_default && (
                        <span className="mt-1 inline-block rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                          {t('pages.addresses.primaryBadge')}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-col gap-1">
                      {!a.is_default && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSetPrimary(a.id)}
                        >
                          {t('pages.addresses.makePrimary')}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setMode({ kind: 'edit', address: a })}
                      >
                        {t('pages.addresses.edit')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-destructive"
                        onClick={() => handleDelete(a.id)}
                      >
                        {t('pages.addresses.delete')}
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <Button onClick={() => setMode({ kind: 'create' })}>
            {t('pages.addresses.addButton')}
          </Button>
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

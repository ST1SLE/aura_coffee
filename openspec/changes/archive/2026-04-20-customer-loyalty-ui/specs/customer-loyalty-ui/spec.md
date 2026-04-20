## ADDED Requirements

### Requirement: Loyalty API client
The customer SPA SHALL expose a typed loyalty API client module at `web/customer/src/api/loyalty.ts` that wraps the existing backend loyalty endpoints, uses the shared authenticated `client`, and validates responses with zod.

#### Scenario: Fetch balance
- **WHEN** a caller invokes `getLoyaltyBalance()`
- **THEN** the module issues `GET /api/v1/profile/loyalty` with JWT auth and returns a zod-validated object `{ balance: number, lifetime_accrued: number }`

#### Scenario: Fetch transactions page
- **WHEN** a caller invokes `listLoyaltyTransactions(page, per_page)`
- **THEN** the module issues `GET /api/v1/profile/loyalty/transactions?page=<page>&per_page=<per_page>` with JWT auth and returns a zod-validated object `{ items: LoyaltyTransaction[], page: number, per_page: number, total: number }`

#### Scenario: Invalid response shape
- **WHEN** the backend returns a payload that does not match the zod schema
- **THEN** the module throws a validation error rather than returning partial or untyped data

### Requirement: Loyalty page route
The customer SPA SHALL expose a protected route `/profile/loyalty` that renders `LoyaltyPage` inside the existing `ProtectedRoute` wrapper and is unreachable for unauthenticated users.

#### Scenario: Authenticated access
- **WHEN** an authenticated customer navigates to `/profile/loyalty`
- **THEN** `LoyaltyPage` mounts and begins fetching balance and transactions

#### Scenario: Unauthenticated access
- **WHEN** an unauthenticated visitor navigates to `/profile/loyalty`
- **THEN** the router redirects to the login flow per existing `ProtectedRoute` behavior

### Requirement: Loyalty page balance header
`LoyaltyPage` SHALL render the current balance as a prominent numeric header with a localized suffix ("баллов" / "points") and a subline showing the lifetime accrued total.

#### Scenario: Balance and lifetime rendered
- **WHEN** balance fetch resolves with `{ balance: 240, lifetime_accrued: 1200 }`
- **THEN** the header displays "240" with the localized points suffix and a subline rendering the localized lifetime label together with the value `1200`

### Requirement: Loyalty page transaction history
`LoyaltyPage` SHALL render a paginated list of the customer's loyalty transactions using `useInfiniteQuery` and display `TransactionRow` for each item.

#### Scenario: Empty history
- **WHEN** the first transactions page returns `{ items: [], total: 0 }`
- **THEN** the page shows the localized empty-state copy and no list rows

#### Scenario: Load more pages
- **WHEN** the customer triggers the "load more" affordance and the previous page was full (`items.length === per_page`)
- **THEN** `LoyaltyPage` fetches the next page and appends the new rows to the list

#### Scenario: No further pages
- **WHEN** the most recently fetched page returned fewer than `per_page` items
- **THEN** `LoyaltyPage` does not request further pages

### Requirement: Transaction row rendering
`TransactionRow` SHALL render each `LoyaltyTransaction` with date, localized type label, optional description and order link, amount with sign-based color, and `balance_after` value.

#### Scenario: Positive amount
- **WHEN** `amount > 0`
- **THEN** the amount is rendered in green with a leading `+`

#### Scenario: Negative amount
- **WHEN** `amount < 0`
- **THEN** the amount is rendered in red with the existing sign

#### Scenario: Zero amount
- **WHEN** `amount === 0`
- **THEN** the amount is rendered in the default (black) color with no added sign

#### Scenario: Linked order
- **WHEN** a transaction has a non-null `order_id`
- **THEN** `TransactionRow` renders a link to `/orders/{order_id}` labeled with the localized "Order #" prefix and the first eight characters of the UUID

#### Scenario: Unlinked transaction
- **WHEN** a transaction has `order_id = null`
- **THEN** no order link is rendered

#### Scenario: Localized type label
- **WHEN** a transaction has `type` in {`accrual`, `redemption`, `reversal`, `admin_adjustment`}
- **THEN** the row displays the matching localized label from `pages.loyalty.txType.*`

### Requirement: Profile loyalty entry-point card
The customer `/profile` page SHALL render a `LoyaltyCard` component between the language selector and the logout button, showing the current balance and a link to `/profile/loyalty`.

#### Scenario: Card renders balance and link
- **WHEN** the balance query resolves with `{ balance: 240, lifetime_accrued: 1200 }` and the customer visits `/profile`
- **THEN** `LoyaltyCard` renders `240` as the balance value and a link whose target is `/profile/loyalty`

#### Scenario: Cache reuse between card and page
- **WHEN** the customer navigates from `/profile` (with `LoyaltyCard` already loaded) to `/profile/loyalty`
- **THEN** `LoyaltyPage` reads the same cached balance via the shared React Query key and does not trigger a duplicate balance fetch

### Requirement: Loyalty UI localization
All user-visible strings added by this change SHALL be provided in both Russian and English via `web/customer/src/i18n/locales/{ru,en}.json` under the `pages.profile.loyaltyCard.*` and `pages.loyalty.*` namespaces.

#### Scenario: Russian locale
- **WHEN** the active locale is `ru`
- **THEN** the loyalty page title, balance suffix, lifetime label, history title, empty-state copy, load-more label, transaction type labels, and row metadata are rendered in Russian

#### Scenario: English locale
- **WHEN** the active locale is `en`
- **THEN** the same keys render their English equivalents with identical semantics

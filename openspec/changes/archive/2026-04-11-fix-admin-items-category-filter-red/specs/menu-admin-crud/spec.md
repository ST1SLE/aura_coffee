## ADDED Requirements

### Requirement: Admin items list supports server-side category filtering

The `GET /api/v1/admin/menu/items` endpoint SHALL accept an optional `category_id` query parameter of type positive integer (`gt=0`). When the parameter is omitted, the endpoint SHALL return all menu items ordered by `(sort_order, id)` as before. When the parameter is supplied, the endpoint SHALL return only menu items whose `category_id` column equals the supplied value, preserving the same ordering. Supplying a `category_id` that does not exist SHALL yield HTTP 404 with detail `"category not found"`. Supplying a non-integer or non-positive value SHALL yield HTTP 422 via Pydantic validation. The parameter SHALL NOT alter RBAC: roles `admin` and `barista` may call the endpoint with or without the filter; all other roles SHALL continue to receive HTTP 403.

_References: PDD §5.2 (Menu tables), PDD §7.1 Phase 6 (Admin Panel). Extends the existing "Admin menu items CRUD" requirement without altering its existing scenarios._

#### Scenario: No filter returns all items
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items` with no query string
- **AND** the database contains items across multiple categories
- **THEN** the response SHALL be HTTP 200 and the list SHALL contain every seeded item

#### Scenario: Filter by existing category returns only matching items
- **GIVEN** two categories A and B each with two items
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=<A.id>`
- **THEN** the response SHALL be HTTP 200 and the list SHALL contain exactly the two items belonging to category A and none from category B

#### Scenario: Filter by nonexistent category returns 404
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=999999` and no category with that id exists
- **THEN** the response SHALL be HTTP 404 with detail `"category not found"`

#### Scenario: Filter by non-positive id is rejected by validation
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=0`
- **THEN** the response SHALL be HTTP 422

#### Scenario: Filter by non-integer id is rejected by validation
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=abc`
- **THEN** the response SHALL be HTTP 422

#### Scenario: Barista may also filter
- **WHEN** an authenticated `barista` sends `GET /api/v1/admin/menu/items?category_id=<A.id>` against an existing category
- **THEN** the response SHALL be HTTP 200 with the filtered list

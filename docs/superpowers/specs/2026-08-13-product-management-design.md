# Product Management Design

## Scope

Phase 3 introduces a dedicated `products` app with server-rendered list, detail, create, edit, deactivate, search, pagination, stock-status, and active-status behavior. Inventory movements, customers, sales, invoices, reports, APIs, Docker, and deployment remain excluded.

## Data model

`Product` stores a required unique uppercase SKU, name, two-decimal selling and cost prices, current stock, low-stock threshold, active status, and creation/update timestamps. Monetary fields use `DecimalField`; validators and PostgreSQL check constraints reject negative prices and stock values. A database constraint requires uppercase stored SKUs.

A product is low stock only when it is active, its current stock is greater than zero, and current stock is less than or equal to its threshold. An active product with zero stock is out of stock. Normal product-management flows never physically delete rows.

## Authorization

Anonymous users are redirected to login. Superusers can list, view, create, edit, and deactivate products. Members of the existing `Staff` group can list and view active products only; inactive detail requests return 404. Authenticated users without an approved role receive 403. Authorization is enforced in views independently of navigation visibility.

## User interface and flows

Use Django generic class-based views, `ModelForm`, and the existing Bootstrap base template. List results show SKU, name, selling price, stock quantity/status, active status, and role-appropriate actions. Deactivation has a dedicated POST-only, CSRF-protected endpoint and is idempotent.

Search uses a trimmed `q` query parameter and Django `Q` expressions across SKU and name. Results paginate at 20 rows and preserve `q` in pagination links. Admin querysets include inactive rows; Staff querysets exclude them.

## Phase 4 boundary

Phase 3 permits Admin to edit `current_stock` directly because StockMovement does not exist. Phase 4 must remove direct stock editing from Product forms and route stock changes through a transactional inventory service that records a movement and locks the Product row during concurrent changes.

## Verification

PostgreSQL-backed tests cover normalization, validation, constraints, stock status, CRUD, deactivation, authentication, authorization, inactive visibility, CSRF, search, pagination, query preservation, navigation, and all Phase 1/2 regressions.

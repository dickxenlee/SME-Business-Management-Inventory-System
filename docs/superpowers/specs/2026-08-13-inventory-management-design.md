# Inventory Management Design

## Scope

Phase 4 adds auditable Stock In, Stock Out, Stock Adjustment, and movement history. It does not add Customers, Sales, Invoice, Reports, REST API, Docker, deployment, returns, sale references, generic relations, or additional movement types.

## Architecture

Create a dedicated `inventory` Django app. `Product.current_stock` remains the efficient current balance, while immutable `StockMovement` rows provide the audit trail. All application stock changes go through `inventory.services`; Product forms and Django admin cannot edit stock directly.

## StockMovement

`StockMovement` contains:

- `product`: protected foreign key to Product.
- `movement_type`: `STOCK_IN`, `STOCK_OUT`, or `ADJUSTMENT`.
- `quantity`: positive integer magnitude.
- `previous_stock` and `new_stock`: non-negative integers.
- `reason`: optional for Stock In/Out and required by the Adjustment form/service.
- `performed_by`: nullable user foreign key using `SET_NULL` so history survives user deletion.
- `created_at`: indexed creation timestamp.

Database constraints enforce only `quantity > 0`, `previous_stock >= 0`, and `new_stock >= 0`. The service enforces movement arithmetic and rejects no-op or negative-result operations.

## Stock service

Public functions `stock_in()`, `stock_out()`, and `adjust_stock()` accept a Product ID, quantity/final stock, acting user, and reason. Each operation uses `transaction.atomic()`, reloads the Product using `select_for_update()`, validates the locked state, updates `Product.current_stock`, and creates exactly one StockMovement. Any exception rolls back both writes.

Inactive Products reject every stock operation. Stock Out rejects quantities greater than current stock. Adjustment accepts the final desired stock, requires a reason, and stores the absolute difference as positive `quantity`; a no-change adjustment is invalid.

## Product integration and migration

Product create/edit forms omit `current_stock`, and new Products therefore start at zero. Product Django admin displays `current_stock` as read-only. Existing non-zero balances are preserved and receive one data-migration StockMovement with previous stock zero, new stock equal to the stored balance, no user, and reason `Opening balance migrated from Phase 3`.

## Authorization and UI

Superusers can view history, Stock In, Stock Out, and Adjustment. Members of the existing Staff group can view permitted history, Stock In, and Stock Out, but receive HTTP 403 for Adjustment. Authenticated users without either role receive HTTP 403; anonymous users are redirected to login. Staff history excludes movements for inactive Products, while superusers may see them.

Server-rendered Bootstrap pages live under `/inventory/`. History supports SKU/name search, movement-type filtering, and pagination at 20 rows while preserving filters. Product details link to allowed inventory operations with the Product preselected. StockMovement Django admin is read-only.

## Transaction and concurrency safety

The Product row lock is acquired before using the current balance. PostgreSQL serializes concurrent changes to the same Product, so each movement uses the balance committed by the preceding operation. A `TransactionTestCase` uses separate connections/threads to verify a consistent movement chain and final balance.

Future Sales code must call the same inventory service. A future multi-product Sale should lock Product rows in stable primary-key order. Sale references, returns, reversals, and fractional quantities are intentionally deferred.

## Testing

Tests cover model invariants, service arithmetic, inactive and insufficient-stock rejection, required adjustment reasons, rollback in both failure directions, concurrent updates, permissions and CSRF, Product integration, opening-balance migration, read-only admin behavior, and history search/filter/pagination. The full Phase 1-3 regression suite must remain green.

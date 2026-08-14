# Sales Management Design

## Scope

Phase 6 adds server-rendered Sales Management only. A Sale is created once as a completed, immutable record. There is no edit, cancel, delete, return, refund, discount, tax, payment, Invoice, Report, REST API, Docker, deployment, or multiple-currency behavior.

## Data model

`Sale` stores an optional protected Customer reference, Customer name/address snapshots, a stored non-negative total, the creating user, and its creation timestamp. Its human-readable number is derived from its primary key as `SALE-{pk:06d}`. The creation timestamp is the sale date/time; there is no separate status or update timestamp.

`SaleItem` belongs to Sale with `on_delete=CASCADE`. It stores a protected Product reference, protected OneToOne StockMovement reference, SKU/name snapshots, positive quantity, non-negative unit-price snapshot, and non-negative subtotal. A Product may appear only once per Sale.

## Creation and inventory transaction

Only the centralized `create_sale(*, customer_id, items, created_by)` service creates Sales. It opens one outer `transaction.atomic()`, locks an optional Customer, locks all unique Products in primary-key order, validates all lines, snapshots current metadata/prices, and calculates every subtotal and the final total. It then creates the Sale, calls the existing `stock_out()` for each Product in the same order with reason `Sale <sale_number>`, and creates each SaleItem linked to the returned movement.

The nested Inventory transaction participates in the outer transaction. Any validation or database failure rolls back the Sale, every SaleItem, every StockMovement, and every Product balance. Sales never update `Product.current_stock` directly.

The service rejects an accumulated total above the capacity of `DecimalField(max_digits=24, decimal_places=2)` before creating the Sale, returning a normal Sales validation error instead of a PostgreSQL numeric-overflow response.

## Rules

- New Sales may select an active Customer or use no Customer for a walk-in.
- Only active Products may be selected, and locked stock must cover the requested quantity.
- The server always uses the locked Product selling price; no submitted price is accepted.
- Customer name/address and Product SKU/name/price snapshots never change after creation.
- Completed Sales have no edit, cancel, or delete routes and are read-only in Django admin.
- Admin superusers and members of the existing `Staff` group may list, create, and view Sales. Anonymous users are redirected to login; other authenticated users receive HTTP 403.

## UI and querying

The Sales app provides list, create, and detail pages using Bootstrap. Creation combines an optional Customer form with a Django formset of Product/quantity rows. Active choices are evaluated per request, duplicate Products are rejected, and a small framework-free script may add or remove formset rows.

The list uses 20 rows per page. `q` searches derived Sale number or Customer name snapshot, and `date` filters the exact local creation date. Both parameters persist across pagination.

## Integrity and future Invoice support

PostgreSQL constraints enforce non-negative totals/prices/subtotals, positive quantities, and one Product per Sale. Cross-row arithmetic remains in the Sales service with integration tests. Phase 7 can use the immutable sale timestamp, Customer snapshots, total, and item SKU/name/price/quantity/subtotal snapshots, while defining its own Invoice number and issuance rules.

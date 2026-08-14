# Inventory Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add transactional, auditable inventory operations and movement history while preventing direct Product stock editing.

**Architecture:** A dedicated `inventory` app owns the immutable StockMovement audit model and the only application service permitted to change `Product.current_stock`. PostgreSQL row locks and atomic transactions keep Product balances and movements consistent.

**Tech Stack:** Django 5.2, PostgreSQL, Bootstrap 5, Django TestCase/TransactionTestCase

**Spec:** `docs/superpowers/specs/2026-08-13-inventory-management-design.md`

## Global Constraints

- Implement Phase 4 Inventory Management only.
- Keep dependencies unchanged.
- Database constraints cover only positive quantity and non-negative stock snapshots.
- All normal stock changes go through `inventory.services`.
- Admin is a Django superuser; Staff is membership in the existing `Staff` group.
- Use server-rendered Django views, Bootstrap, CSRF protection, and 20-row pagination.

---

### Task 1: StockMovement model and opening balances

**Files:**
- Create: `inventory/__init__.py`, `inventory/apps.py`, `inventory/models.py`, `inventory/migrations/__init__.py`
- Create: `inventory/migrations/0001_initial.py`, `inventory/migrations/0002_backfill_opening_stock.py`
- Modify: `sme_manager/settings.py`
- Test: `inventory/tests/test_models.py`, `inventory/tests/test_migrations.py`

**Interfaces:**
- Produces: `StockMovement`, `StockMovement.MovementType`, and an opening-balance migration for existing non-zero Product stock.

- [x] Write failing tests for choices, timestamps, user/product relationships, ordering, and the three simple database constraints.
- [x] Run `python manage.py test inventory.tests.test_models` and confirm model/import failures.
- [x] Implement the model and initial migration with `quantity__gt=0`, `previous_stock__gte=0`, and `new_stock__gte=0` constraints.
- [x] Write and run a `MigrationExecutor` test proving zero-stock Products get no opening movement and non-zero Products get exactly one without changing their balance.
- [x] Implement the reversible opening-balance data migration and rerun model/migration tests.

### Task 2: Transactional inventory service

**Files:**
- Create: `inventory/services.py`
- Test: `inventory/tests/test_services.py`, `inventory/tests/test_transactions.py`

**Interfaces:**
- Produces: `stock_in(*, product_id, quantity, performed_by, reason="")`, `stock_out(...)`, `adjust_stock(*, product_id, new_stock, performed_by, reason)`, and `InventoryOperationError`.

- [x] Write failing tests for successful Stock In/Out/Adjustment, positive magnitude, snapshots, user, reason, timestamp, inactive Products, excessive Stock Out, negative input, and no-op Adjustment.
- [x] Run the service tests and confirm missing-service failures.
- [x] Implement one private atomic mutation function that locks the Product with `select_for_update()`, validates locked state, updates stock, and creates one movement.
- [x] Run service tests until green.
- [x] Write failure-injection tests proving movement-create failure rolls back Product stock and Product-update failure leaves no movement.
- [x] Add a PostgreSQL concurrency `TransactionTestCase` using separate connections and threads; assert a correct final balance and chained snapshots.
- [x] Run transaction tests until green.

### Task 3: Inventory forms, authorization, views, and URLs

**Files:**
- Create: `inventory/forms.py`, `inventory/mixins.py`, `inventory/views.py`, `inventory/urls.py`
- Modify: `sme_manager/urls.py`
- Test: `inventory/tests/test_permissions.py`, `inventory/tests/test_views.py`

**Interfaces:**
- Consumes: the three inventory service functions.
- Produces: `inventory:history`, `inventory:stock_in`, `inventory:stock_out`, and `inventory:adjustment`.

- [x] Write failing form/view tests for active Product selection, positive quantities, required Adjustment reason, successful POST redirects/messages, invalid operation errors, and preselected Product query parameters.
- [x] Write failing permission tests for anonymous redirects, role-based access, Staff Adjustment denial, unassigned-user 403, inactive Product rejection, and CSRF rejection.
- [x] Implement Bootstrap ModelChoice/forms, access mixins, service-backed form views, URLs, and root URL inclusion.
- [x] Run permission and view tests until green.

### Task 4: Movement history and Bootstrap UI

**Files:**
- Create: `inventory/templates/inventory/movement_list.html`, `inventory/templates/inventory/movement_form.html`
- Modify: `templates/base.html`, `products/templates/products/product_detail.html`
- Test: `inventory/tests/test_history.py`

**Interfaces:**
- Produces: searchable/filterable movement history and Product-detail inventory shortcuts.

- [x] Write failing tests for displayed movement columns, Staff inactive-product exclusion, Admin inclusion, SKU/name search, type filter, combined filters, 20-row pagination, and preserved query parameters.
- [x] Implement `select_related` history querying, context values, Bootstrap history/form templates, navigation, and role-aware Product actions.
- [x] Run history tests until green.

### Task 5: Lock down direct stock editing and admin

**Files:**
- Modify: `products/forms.py`, `products/admin.py`
- Create: `inventory/admin.py`
- Modify tests: `products/tests/test_forms.py`, `products/tests/test_views.py`
- Test: `inventory/tests/test_product_integration.py`, `inventory/tests/test_permissions.py`

**Interfaces:**
- Produces: zero-stock Product creation, ignored rogue stock form input, read-only Product stock admin, and read-only StockMovement admin.

- [x] Change existing Product expectations so create/edit never accepts `current_stock` and new Products start at zero.
- [x] Write failing tests for rogue stock POST data, Product admin read-only stock, and StockMovement admin add/change/delete denial.
- [x] Remove `current_stock` from ProductForm, add it to ProductAdmin read-only fields, and register read-only StockMovement admin.
- [x] Run Product and integration/admin tests until green.

### Task 6: Documentation and full verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: Phase 4 usage and permission documentation.

- [x] Update README with Inventory roles, operation workflow, audit behavior, and Product stock-edit restriction.
- [x] Run `python manage.py check`.
- [x] Run `python manage.py makemigrations --check`.
- [x] Run `python manage.py migrate` and verify the real opening-balance result.
- [x] Run `python manage.py test`.
- [x] Run `git diff --check`.
- [x] Manually exercise Stock In, Stock Out, Adjustment, permission rejection, inactive rejection, history filtering, and rollback-safe invalid operations against PostgreSQL without leaving sample data.
- [x] Audit the diff for excluded Phase 5+ modules and report Git status without committing.

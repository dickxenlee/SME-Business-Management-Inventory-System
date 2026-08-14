# Sales Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immutable, transactional Sales creation with historical snapshots and auditable Inventory deductions.

**Architecture:** A dedicated `sales` app owns Sale and SaleItem. A centralized outer-atomic service locks Products deterministically, calculates server-controlled monetary snapshots, reuses `inventory.stock_out()`, and links each returned StockMovement to its SaleItem.

**Tech Stack:** Django 5.2, PostgreSQL, Django ORM transactions/formsets/class-based views, Bootstrap 5.

**Spec:** `docs/superpowers/specs/2026-08-14-sales-management-design.md`

## Global Constraints

- Implement Sales Management only; do not implement Phase 7 or excluded financial workflows.
- Never update `Product.current_stock` outside the existing Inventory service.
- Keep Sale creation inside one outer `transaction.atomic()` and lock Products by ascending primary key.
- Keep completed Sales immutable in normal URLs and Django admin.
- Do not add dependencies or commit Phase 6 automatically.

---

### Task 1: Sale and SaleItem persistence

**Files:**
- Create: `sales/__init__.py`, `sales/apps.py`, `sales/models.py`, `sales/migrations/__init__.py`, `sales/migrations/0001_initial.py`
- Modify: `sme_manager/settings.py`
- Test: `sales/tests/test_models.py`

**Interfaces:**
- Produces: `Sale.sale_number`, `Sale.items`, and `SaleItem.stock_movement` for services and views.

- [ ] Write model tests for valid records, derived numbers, walk-ins, constraints, uniqueness, snapshots, ownership cascade, and protected Customer/Product/StockMovement deletion.
- [ ] Run `python manage.py test sales.tests.test_models` and confirm failure because the Sales models do not exist.
- [ ] Implement the models, named constraints, app registration, and matching initial migration.
- [ ] Rerun the model tests and confirm they pass.

### Task 2: Sale input forms

**Files:**
- Create: `sales/forms.py`
- Test: `sales/tests/test_forms.py`

**Interfaces:**
- Produces: `SaleForm`, `SaleItemForm`, and `SaleItemFormSet` containing only `customer`, `product`, and `quantity` input.

- [ ] Write tests for optional/active Customer choices, active Product choices, positive quantity, no submitted price field, at least one line, and duplicate Product rejection.
- [ ] Run `python manage.py test sales.tests.test_forms` and confirm failure because forms do not exist.
- [ ] Implement per-request querysets, Bootstrap widgets, Product option labels, and formset-wide validation.
- [ ] Rerun the form tests and confirm they pass.

### Task 3: Transactional Sales service

**Files:**
- Create: `sales/services.py`
- Test: `sales/tests/test_services.py`, `sales/tests/test_transactions.py`, `sales/tests/test_history.py`

**Interfaces:**
- Produces: `create_sale(*, customer_id, items, created_by) -> Sale` and `SalesOperationError`.
- Consumes: `inventory.services.stock_out(*, product_id, quantity, performed_by, reason)`.

- [ ] Write service tests for one/multiple lines, totals, maximum-total overflow, all snapshots, walk-in/existing Customer, creator, active checks, missing records, duplicate lines, and one movement per item.
- [ ] Write rollback tests for insufficient stock and failures after earlier lines have changed stock.
- [ ] Write historical tests proving later metadata edits/deactivation do not change snapshots or break detail data.
- [ ] Run the focused tests and confirm failure because `create_sale()` does not exist.
- [ ] Implement input normalization, Customer lock, sorted Product locks, full prevalidation/calculation, Sale creation, ordered `stock_out()` calls, and SaleItem creation within one outer atomic block.
- [ ] Rerun the focused tests and confirm they pass.

### Task 4: PostgreSQL concurrency

**Files:**
- Create: `sales/tests/test_concurrency.py`

**Interfaces:**
- Exercises: the public `create_sale()` service using independent database connections.

- [ ] Write `TransactionTestCase` thread tests for competing limited stock and overlapping multi-Product Sales submitted in reverse order.
- [ ] Run the concurrency tests and confirm they expose overselling/deadlock if deterministic locking is absent.
- [ ] Adjust only the Sales locking/order behavior needed to pass; do not refactor Inventory.
- [ ] Rerun and confirm correct final balances, movement chains, and no live/deadlocked threads.

### Task 5: Authorization, URLs, views, and server-rendered UI

**Files:**
- Create: `sales/mixins.py`, `sales/urls.py`, `sales/views.py`
- Create: `sales/templates/sales/sale_list.html`, `sales/templates/sales/sale_detail.html`, `sales/templates/sales/sale_form.html`
- Modify: `sme_manager/urls.py`, `templates/base.html`
- Test: `sales/tests/test_permissions.py`, `sales/tests/test_views.py`, `sales/tests/test_search_pagination.py`

**Interfaces:**
- Produces routes `sales:list`, `sales:create`, and `sales:detail`; consumes forms and `create_sale()`.

- [ ] Write permission tests for anonymous, Admin, Staff, and unassigned users plus absence of edit/cancel/delete routes.
- [ ] Write view tests for valid/invalid/CSRF creation, list/detail rendering, and service errors.
- [ ] Write `q` Sale-number/Customer search, exact `date` filtering, 20-row pagination, and query-preservation tests.
- [ ] Run the focused tests and confirm failures because routes/views/templates do not exist.
- [ ] Implement class-based views with `select_related`/`prefetch_related`, POST coordination of form plus formset, messages, and server-side authorization.
- [ ] Implement Bootstrap templates and the minimal formset-row script; add root routing and navigation.
- [ ] Rerun the focused tests and confirm they pass.

### Task 6: Read-only administration, documentation, and complete verification

**Files:**
- Create: `sales/admin.py`
- Modify: `README.md`
- Test: `sales/tests/test_admin.py`

**Interfaces:**
- Produces: read-only Sale/SaleItem administrative visibility with no add/change/delete bypass.

- [ ] Write admin tests proving GET visibility and rejection of add/change/delete actions.
- [ ] Run the admin tests and confirm failure before registration/read-only behavior exists.
- [ ] Register Sale with a read-only SaleItem inline and disable all mutations; document Sales behavior.
- [ ] Run all Sales tests, then all existing tests.
- [ ] Run `python manage.py check`, `python manage.py makemigrations --check`, `python manage.py migrate`, `python manage.py test`, and `git diff --check`.
- [ ] Inspect `git status`, report the uncommitted Phase 6 scope, and recommend `feat: add transactional sales management` without starting Phase 7.

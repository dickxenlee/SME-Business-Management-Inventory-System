# Product Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PostgreSQL-backed Product Management module with role-controlled CRUD, soft deactivation, search, pagination, and stock-status behavior.

**Architecture:** Add one focused `products` Django app. Keep domain validation in the Product model and ProductForm, enforce critical invariants with database constraints, and implement server-rendered generic views with reusable role mixins.

**Tech Stack:** Python 3.11, Django 5.2 LTS, PostgreSQL, Bootstrap 5

**Spec:** `docs/superpowers/specs/2026-08-13-product-management-design.md`

## Global Constraints

- Admin is Django superuser; Staff is membership in the existing `Staff` group.
- Staff can view active products only and receives 404 for inactive product details.
- Deactivation is POST-only, CSRF-protected, preserves the row, and sets `is_active=False`.
- Use `DecimalField`, `ModelForm`, Django ORM search, and pagination of 20 products.
- Keep `current_stock` editable during Phase 3 only.
- Do not implement physical deletion, Inventory, StockMovement, Customers, Sales, Invoice, Reports, REST API, Docker, or deployment.

---

### Task 1: Product model and constraints

**Files:** Create `products/models.py`, `products/apps.py`, `products/admin.py`, `products/migrations/0001_initial.py`, and `products/tests/test_models.py`; modify `sme_manager/settings.py`.

**Interfaces:** Produces `Product`, `Product.is_low_stock`, `Product.is_out_of_stock`, uppercase SKU normalization, and database constraints for all non-negative fields and uppercase SKU storage.

- [x] Write model tests for valid data, required/unique/normalized SKU, negative values, stock statuses, and row-preserving deactivation.
- [x] Run the model tests and verify they fail because the Product app/model is absent.
- [x] Implement the minimal model, registration, and migration.
- [x] Run model tests against PostgreSQL until green.

### Task 2: Product form and CRUD authorization

**Files:** Create `products/forms.py`, `products/mixins.py`, `products/urls.py`, `products/views.py`, `products/tests/test_forms.py`, `products/tests/test_permissions.py`, and `products/tests/test_views.py`; modify `sme_manager/urls.py`.

**Interfaces:** Produces `ProductForm`, read/admin access mixins, list/detail/create/update views, and POST-only `ProductDeactivateView`.

- [x] Write form, CRUD, anonymous, Admin, Staff, inactive visibility, GET/POST deactivation, and CSRF tests.
- [x] Run the tests and verify failures for missing forms/routes/views.
- [x] Implement ModelForm, role mixins, URLs, generic views, and deactivate behavior.
- [x] Rerun Product form/view/permission tests until green.

### Task 3: Search, pagination, and Bootstrap templates

**Files:** Create `products/tests/test_search_pagination.py` and templates under `products/templates/products/`; modify `templates/base.html`, `static/css/app.css`, and `README.md`.

**Interfaces:** Produces SKU/name search via `q`, 20-item pages, search-preserving links, stock badges, status labels, role-aware actions, and Products navigation.

- [x] Write search, no-result, pagination-size, page-content, query-preservation, inactive-filter, and navigation tests.
- [x] Run tests and verify template/search failures.
- [x] Implement Bootstrap templates, queryset filtering, pagination, navigation, and documentation.
- [x] Rerun all Product tests until green.

### Task 4: Migration and full verification

**Files:** Verify all Phase 3 files and existing Phase 1/2 files without unrelated changes.

**Interfaces:** Produces an applied `products.0001_initial` migration and a verified complete test suite.

- [x] Run `manage.py check`, `manage.py makemigrations --check`, `manage.py migrate`, `manage.py test`, and `git diff --check`.
- [x] Verify Product constraints and Staff/Admin visibility against the development PostgreSQL database.
- [x] Exercise login, create, edit, search, detail, and deactivate over local HTTP where practical.
- [x] Audit the filesystem to confirm excluded Phase 4+ modules were not created.

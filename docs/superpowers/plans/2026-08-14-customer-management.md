# Customer Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add simple, secure Customer management that is ready for a future optional Sale-to-Customer relationship.

**Architecture:** A dedicated `customers` app owns the Customer model, form, permissions, views, templates, admin, and tests. It follows existing Product list/detail/form/deactivation patterns while allowing Staff to create and edit active Customers.

**Tech Stack:** Django 5.2, PostgreSQL, Bootstrap 5, Django TestCase

**Spec:** `docs/superpowers/specs/2026-08-14-customer-management-design.md`

## Global Constraints

- Implement Phase 5 Customer Management only.
- Do not add dependencies, Sales models, customer codes, deduplication, or snapshot fields.
- Phone and email are optional and non-unique.
- Use server-side authorization, POST/CSRF deactivation, soft deletion, ORM search, and 20-row pagination.
- All existing 133 Phase 1–4 tests must continue passing.

---

### Task 1: Customer model, validation, migration, and admin

**Files:**
- Create: `customers/__init__.py`, `customers/apps.py`, `customers/models.py`, `customers/admin.py`
- Create: `customers/migrations/__init__.py`, `customers/migrations/0001_initial.py`
- Modify: `sme_manager/settings.py`
- Test: `customers/tests/test_models.py`, `customers/tests/test_admin.py`

**Interfaces:**
- Produces: `Customer` with required trimmed name, optional validated contacts, active status, timestamps, and deletion-protected admin.

- [ ] Write failing model tests for valid records, blank/whitespace name, phone formats, invalid phone, optional contacts, duplicates, active default, timestamps, and row-preserving deactivation.
- [ ] Run model tests and confirm the missing Customer model failure.
- [ ] Implement the model, app configuration, initial migration, and settings registration.
- [ ] Run model tests until green.
- [ ] Write a failing Django-admin deletion test, register useful Customer list/search/filter fields, disable physical deletion, and rerun tests.

### Task 2: Customer ModelForm

**Files:**
- Create: `customers/forms.py`
- Test: `customers/tests/test_forms.py`

**Interfaces:**
- Produces: `CustomerForm` exposing only `name`, `phone`, `email`, and `address` with Bootstrap widgets.

- [ ] Write failing form tests for trimming, required name, valid/invalid email, valid/invalid phone, optional contacts, duplicates, entered-value preservation, and hidden active status.
- [ ] Run form tests and confirm the missing form failure.
- [ ] Implement the minimal ModelForm and rerun tests until green.

### Task 3: Authorization, CRUD views, and deactivation

**Files:**
- Create: `customers/mixins.py`, `customers/views.py`, `customers/urls.py`
- Modify: `sme_manager/urls.py`
- Test: `customers/tests/test_permissions.py`, `customers/tests/test_views.py`

**Interfaces:**
- Produces: `customers:list`, `customers:create`, `customers:detail`, `customers:edit`, and `customers:deactivate`.

- [ ] Write failing permission tests for anonymous, Admin, Staff, unassigned users, inactive Staff detail/edit 404, and Staff deactivation 403.
- [ ] Write failing view tests for list/detail/create/edit, invalid create, POST deactivation, GET 405, CSRF 403, idempotency, and row preservation.
- [ ] Run the tests and confirm missing URL/view failures.
- [ ] Implement access mixins, class-based views, URL routes, role-filtered querysets, and POST-only deactivation.
- [ ] Rerun permission/view tests until green.

### Task 4: Search, pagination, and Bootstrap templates

**Files:**
- Create: `customers/templates/customers/customer_list.html`
- Create: `customers/templates/customers/customer_detail.html`
- Create: `customers/templates/customers/customer_form.html`
- Modify: `templates/base.html`
- Test: `customers/tests/test_search_pagination.py`

**Interfaces:**
- Produces: Customer UI plus `q` search over name/phone/email and 20-row query-preserving pagination.

- [ ] Write failing tests for template rendering, name/phone/email search, no results, 20-row pagination, page two, preserved query, inactive Staff exclusion, and navigation.
- [ ] Run the tests and confirm template/content failures.
- [ ] Implement Bootstrap templates, navigation, ORM search, pagination context, and role-aware actions.
- [ ] Rerun search/UI tests until green.

### Task 5: Documentation, audit, and complete verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: Customer workflow documentation and verified Phase 5 handoff.

- [ ] Document Customer roles, optional contacts, and soft deactivation.
- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py makemigrations --check`.
- [ ] Run `python manage.py migrate`.
- [ ] Run `python manage.py test`.
- [ ] Run `git diff --check` and audit that no Phase 6 modules exist.
- [ ] Manually exercise Customer create/edit/search/deactivate and role restrictions in a rollback transaction.
- [ ] Report Git status and recommend `feat: add customer management module` without committing Phase 5.

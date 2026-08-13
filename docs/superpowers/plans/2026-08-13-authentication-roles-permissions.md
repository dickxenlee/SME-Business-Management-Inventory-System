# Authentication, Roles, and Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Django-native login, logout, Admin/Staff roles, server-side dashboard authorization, and tested Django-admin access boundaries.

**Architecture:** Retain Django's built-in User model and use superuser status for Admin plus a migration-created Staff group for business staff. Use built-in authentication class-based views and a small server-side predicate for dashboard authorization.

**Tech Stack:** Python 3.11, Django 5.2 LTS, PostgreSQL, Bootstrap 5

**Spec:** `docs/superpowers/specs/2026-08-13-authentication-roles-permissions-design.md`

## Global Constraints

- Normal Staff users belong to the `Staff` group and retain `is_staff=False`.
- Do not add a custom User model, role model, public registration, password reset, social login, or JWT.
- Do not add Products, Inventory, Customers, Sales, Invoice, Reports, REST API, or Docker.
- Enforce authorization server-side and retain Django CSRF, password hashing, sessions, and cookie defaults.
- Logout accepts POST only.

---

### Task 1: Seed the Staff role

**Files:**
- Create: `core/migrations/0001_create_staff_group.py`
- Create: `core/tests/test_roles.py`

**Interfaces:**
- Consumes: Django's historical `auth.Group` model.
- Produces: An idempotent data migration ensuring a group named `Staff` exists.

- [x] **Step 1: Write a database test asserting the Staff group exists**
- [x] **Step 2: Run the test and verify it fails before the migration exists**
- [x] **Step 3: Add a `RunPython` data migration using `Group.objects.get_or_create(name="Staff")`**
- [x] **Step 4: Apply migrations and rerun the test**

### Task 2: Protect the dashboard by role

**Files:**
- Create: `core/tests/test_permissions.py`
- Modify: `core/views.py`
- Modify: `core/tests/test_views.py`
- Create: `templates/403.html`

**Interfaces:**
- Consumes: Authenticated Django users and the `Staff` group.
- Produces: `is_admin_or_staff(user) -> bool` and a protected `home(request)` returning 200, login redirect, or 403.

- [x] **Step 1: Write tests for anonymous redirect, Staff access, superuser access, and role-less 403**
- [x] **Step 2: Run the tests and verify dashboard protection failures**
- [x] **Step 3: Add `login_required` plus a server-side superuser-or-Staff check**
- [x] **Step 4: Add the Bootstrap 403 template and rerun the tests**

### Task 3: Add built-in login and POST logout

**Files:**
- Create: `core/forms.py`
- Create: `core/tests/test_authentication.py`
- Modify: `core/urls.py`
- Modify: `sme_manager/settings.py`
- Create: `templates/registration/login.html`

**Interfaces:**
- Consumes: Django `AuthenticationForm`, `LoginView`, and `LogoutView`.
- Produces: `/accounts/login/`, `/accounts/logout/`, `BootstrapAuthenticationForm`, and dashboard/login redirects.

- [x] **Step 1: Write tests for login page, valid/invalid/inactive login, safe `next`, POST logout, GET rejection, and CSRF rejection**
- [x] **Step 2: Run the tests and verify missing-route failures**
- [x] **Step 3: Add Bootstrap form presentation, built-in auth URLs, redirects, and login template**
- [x] **Step 4: Rerun the authentication tests**

### Task 4: Update navigation and verify admin boundaries

**Files:**
- Create: `core/tests/test_admin_permissions.py`
- Modify: `templates/base.html`
- Modify: `static/css/app.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: `request.user` authentication, superuser, and staff flags.
- Produces: Role-aware navigation, CSRF-protected logout UI, and documented local staff-management workflow.

- [x] **Step 1: Write tests for role-aware navigation and admin/user-management access**
- [x] **Step 2: Run tests and verify current navigation/access assertions fail**
- [x] **Step 3: Update navigation, styling, and README role instructions**
- [x] **Step 4: Run all required verification commands and audit excluded scope**

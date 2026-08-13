# Authentication, Roles, and Permissions Design

## Scope

Phase 2 adds login, POST-only logout, authenticated dashboard access, Admin and Staff roles, server-side authorization, Django-admin staff management, Bootstrap authentication pages, and automated tests. It excludes registration, password reset, social authentication, JWT, custom user/role models, business modules, REST APIs, and Docker.

## Authentication

Use Django's built-in `auth.User`, password hashing, sessions, `LoginView`, `LogoutView`, and `AuthenticationForm`. Login is available at `/accounts/login/`; logout is available at `/accounts/logout/` and accepts POST only. Successful login returns users to a safe `next` URL or the dashboard, and successful logout returns them to login.

## Roles and authorization

Admin is represented by Django superuser status (`is_superuser=True`, `is_staff=True`). Normal business staff are members of a `Staff` Django Group while retaining `is_staff=False`, so they cannot enter Django admin. The internal dashboard requires an authenticated active user who is either a superuser or a member of the Staff group. Authenticated users without either role receive HTTP 403.

The `Staff` group is created idempotently by a data migration. No custom database table is introduced. Future business-module permissions can be assigned to this group through Django's standard permission system.

## User interface

The shared Bootstrap navigation displays login controls to anonymous users and username plus a CSRF-protected logout form to authenticated users. Only superusers see the Django admin navigation link. The login and permission-denied pages use the existing Bootstrap layout and expose no registration or password-reset links.

## Security

Authorization is enforced in the dashboard view and is not dependent on navigation visibility. CSRF middleware remains enabled, logout requires POST, Django validates redirect destinations, passwords are never stored manually, and session/cookie behavior remains at Django defaults.

## Verification

Database-backed tests cover login success and failure, inactive accounts, safe redirects, POST-only logout and CSRF, anonymous redirects, Staff and superuser access, role-less denial, Django-admin access boundaries, navigation visibility, migration-created group state, and existing 404 behavior. Verification runs Django checks, migration drift detection, migrations, and the full test suite against PostgreSQL.

# Project Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clean Django foundation backed exclusively by PostgreSQL, with environment-based configuration, a Bootstrap layout, a placeholder dashboard, documentation, and foundation tests.

**Architecture:** Use the `sme_manager` Django project package and one `core` app. Keep settings in one conventional module, load local configuration with `python-dotenv`, and keep shared templates and static assets at project level.

**Tech Stack:** Python 3.11, Django 5.2 LTS, PostgreSQL, Psycopg 3, python-dotenv, Bootstrap 5, Git

## Global Constraints

- Create only Phase 1 project-foundation functionality.
- Do not create Products, Inventory, Customers, Sales, Invoice, Reports, REST API, or Docker modules.
- Never commit real credentials or secrets.
- Do not install PostgreSQL automatically.
- Do not use SQLite as a fallback.
- Keep the structure simple and add no dependencies beyond Django, Psycopg, and python-dotenv.

---

### Task 1: Repository and Django configuration

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `manage.py`
- Create: `sme_manager/__init__.py`
- Create: `sme_manager/settings.py`
- Create: `sme_manager/urls.py`
- Create: `sme_manager/asgi.py`
- Create: `sme_manager/wsgi.py`
- Create: `core/__init__.py`
- Create: `core/apps.py`
- Create: `core/admin.py`
- Create: `core/models.py`
- Create: `core/migrations/__init__.py`

**Interfaces:**
- Consumes: Operating-system variables loaded from `.env` by `load_dotenv(BASE_DIR / ".env")`.
- Produces: A Django project configured with `django.db.backends.postgresql` and a registered `core.apps.CoreConfig` application.

- [ ] **Step 1: Initialize Git**

Run `git init` and confirm `git status --short` succeeds.

- [ ] **Step 2: Create dependency and secret-handling files**

Create pinned requirements for `Django==5.2.16`, `psycopg[binary]==3.3.4`, and `python-dotenv==1.2.1`. Ignore `.env`, `.venv/`, Python caches, coverage data, editor metadata, logs, and `staticfiles/`. Put only placeholder values in `.env.example`.

- [ ] **Step 3: Create the project configuration**

Configure `SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]`, explicit boolean parsing for `DJANGO_DEBUG`, comma-separated `DJANGO_ALLOWED_HOSTS`, the PostgreSQL database variables with a five-second connection timeout, project-level templates, `STATIC_URL`, `STATICFILES_DIRS`, and `STATIC_ROOT`.

- [ ] **Step 4: Install dependencies and run a configuration check**

Run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and then `.venv\Scripts\python.exe manage.py check`. Expected result: dependency installation succeeds and Django reports no system-check issues without using SQLite.

### Task 2: Test-drive the home page and navigation

**Files:**
- Create: `core/tests/__init__.py`
- Create: `core/tests/test_views.py`
- Create: `core/views.py`
- Create: `core/urls.py`
- Create: `templates/base.html`
- Create: `templates/core/home.html`
- Create: `static/css/app.css`
- Modify: `sme_manager/urls.py`

**Interfaces:**
- Consumes: Django template engine and the root URL configuration.
- Produces: `core.views.home(request)` registered as `core:home`, rendering `core/home.html` with reusable navigation.

- [ ] **Step 1: Write failing foundation tests**

Create `HomePageTests(SimpleTestCase)` tests asserting that `/` returns 200, uses `core/home.html`, contains a navigation landmark and dashboard heading, and that `/missing-page/` returns 404.

- [ ] **Step 2: Run tests and verify the red state**

Run `.venv\Scripts\python.exe manage.py test core.tests.test_views -v 2`. Expected result: failure because the home route and template do not exist.

- [ ] **Step 3: Implement the minimum home-page behavior**

Add `home()` using `render(request, "core/home.html")`, register it at the app root, include `core.urls` in the project URLs, create the Bootstrap base template with a `<nav>` element, and extend it from the dashboard placeholder.

- [ ] **Step 4: Run tests and verify the green state**

Run `.venv\Scripts\python.exe manage.py test core.tests.test_views -v 2`. Expected result: all foundation view tests pass.

### Task 3: Documentation and final verification

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: The environment-variable names, dependency file, and Django management commands created in Tasks 1 and 2.
- Produces: Reproducible Windows local-setup instructions without real credentials.

- [ ] **Step 1: Document local setup**

Document virtual-environment creation, dependency installation, `.env.example` copying, PostgreSQL database/user creation, migration, testing, static collection, superuser creation, and development-server startup.

- [ ] **Step 2: Run all required verification commands**

Run, in order: `manage.py check`, `manage.py makemigrations --check`, `manage.py migrate`, `manage.py test`, and `manage.py collectstatic --noinput`. Record PostgreSQL absence as a blocker for migration and connection verification; do not substitute SQLite.

- [ ] **Step 3: Verify repository scope and secrets**

Run `git check-ignore .env`, inspect `git status --short`, search paths for excluded module names, and verify `.env.example` contains placeholders only.

- [ ] **Step 4: Review the implementation**

Inspect the final diff, confirm no excluded business app or Docker files exist, and report every verification result and remaining manual PostgreSQL configuration.

# SME Business Management & Inventory System

A portfolio-ready Django foundation for a small-business management system. Phase 1 provides PostgreSQL configuration, a reusable Bootstrap layout, and a dashboard placeholder. Business modules will be added in later phases.

## Requirements

- Python 3.11 or newer
- PostgreSQL
- Git

## Local setup (PowerShell)

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Create a PostgreSQL user and database

Open `psql` as a PostgreSQL administrator and run:

```sql
CREATE USER sme_manager_user WITH PASSWORD 'choose-a-strong-local-password';
CREATE DATABASE sme_manager OWNER sme_manager_user;
```

The application is PostgreSQL-only. It does not fall back to SQLite when PostgreSQL is unavailable.

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated value in `DJANGO_SECRET_KEY` and set the database credentials in `.env`. The `.env` file is ignored by Git. Never commit or share it.

Available settings:

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Required private Django signing key |
| `DJANGO_DEBUG` | `True` for local development; use `False` outside development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names or IP addresses |
| `DB_NAME` | Required PostgreSQL database name |
| `DB_USER` | Required PostgreSQL user |
| `DB_PASSWORD` | Required PostgreSQL password |
| `DB_HOST` | PostgreSQL host; defaults to `localhost` |
| `DB_PORT` | PostgreSQL port; defaults to `5432` |

### 4. Prepare and run Django

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to view the dashboard placeholder.

## Authentication and roles

- **Admin** users are Django superusers. They can access the dashboard, Django admin, and built-in user management.
- **Staff** users belong to the Django group named `Staff`. Keep their Django `is_staff` setting disabled so they cannot access Django admin.

Create the initial administrator with:

```powershell
python manage.py createsuperuser
```

Administrators can create normal users at `/admin/auth/user/` and assign them to the `Staff` group. There is no public registration page.

PostgreSQL-backed tests create a temporary database. The local development database role therefore needs `CREATEDB` while running tests:

```sql
ALTER ROLE sme_manager_user CREATEDB;
```

A production application role should not normally receive this permission.

## Product and inventory management

Authenticated Staff users can search, paginate, list, and view active products. Django superusers can additionally view inactive products, create and edit products, and deactivate products without deleting their database rows.

New Products start with zero stock. Product forms omit stock, while Django admin displays it as read-only; use the Inventory workflow for every change:

- **Admin:** view movement history, Stock In, Stock Out, and Stock Adjustment.
- **Staff:** view permitted movement history, Stock In, and Stock Out.

Stock Adjustment records the final physically counted quantity and requires a reason. Each successful operation updates the Product balance and creates an audit record in one PostgreSQL transaction. Inactive Products reject stock operations.

## Verification

```powershell
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

Generated static output is written to `staticfiles/` and is not committed.

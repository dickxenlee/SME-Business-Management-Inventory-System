# SME Business Management & Inventory System

A portfolio-ready Django and PostgreSQL system for managing SME products, inventory, customers, sales, and immutable invoices through a server-rendered Bootstrap interface.

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
| `DJANGO_ENVIRONMENT` | `development`, `test`, or `production`; defaults to `development` |
| `DJANGO_SECRET_KEY` | Required private Django signing key |
| `DJANGO_DEBUG` | Local/test debug control; production always forces `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names or IP addresses |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins required in production |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | Explicitly trust a verified platform proxy; defaults to `False` |
| `DJANGO_SECURE_HSTS_SECONDS` | Production HSTS rollout value; defaults to `0` |
| `DJANGO_LOG_LEVEL` | Console logging threshold; defaults to `INFO` |
| `DB_NAME` | Required PostgreSQL database name |
| `DB_USER` | Required PostgreSQL user |
| `DB_PASSWORD` | Required PostgreSQL password |
| `DB_HOST` | PostgreSQL host; defaults to `localhost` |
| `DB_PORT` | PostgreSQL port; defaults to `5432` |
| `DB_SSLMODE` | PostgreSQL TLS mode; production requires `require`, `verify-ca`, or `verify-full` |
| `DB_CONNECT_TIMEOUT` | Connection timeout in seconds; defaults to `5` |
| `DB_CONN_MAX_AGE` | Connection reuse in seconds; defaults to `0` locally and `60` in production |
| `INVOICE_SELLER_NAME` | Required seller name copied onto each issued Invoice |
| `INVOICE_SELLER_ADDRESS` | Required seller address copied onto each issued Invoice |

Invoice issuance is rejected when either seller value is empty. These values are snapshotted when an Invoice is issued, so later configuration changes do not alter historical documents.

### 4. Prepare and run Django

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to view the business dashboard.

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

## Customer management

Authenticated Admin and Staff users can create Customers and search the Customer directory by name, phone, or email. Results are paginated at 20 Customers per page.

- **Admin:** view and edit active or inactive Customers, create Customers, and deactivate Customers.
- **Staff:** view and edit active Customers and create Customers. Inactive Customer records are not exposed.

Customer deactivation preserves the database row. Physical Customer deletion is not available through the normal UI or Django admin. Phone, email, and address are optional; duplicate contact details are allowed.

## Sales management

Admin and Staff users can create immutable completed Sales for an active Customer or a walk-in customer. Each Sale may contain multiple active Products. Prices come from the current Product selling price and cannot be overridden through the Sales form.

Sale creation is one PostgreSQL transaction: requested Products are locked in a consistent order, the existing Inventory service deducts stock, and every SaleItem links to its exact StockMovement. If any line is invalid or has insufficient stock, the Sale, all items, all movements, and every stock change are rolled back.

Historical Sales keep Customer name/address and Product SKU/name/price snapshots. Completed Sales are read-only and cannot be edited, cancelled, or deleted through the Sales UI or Django admin.

## Invoice management

Admin and Staff users can manually issue one immutable Invoice from a completed Sale. Issuance copies the historical Sale customer, item, price, and total snapshots together with the configured seller identity in one PostgreSQL transaction. It does not change the Sale, Product stock, or StockMovement history.

Invoices support number, Sale number, customer, and issue-date lookup with 20 records per page. The Invoice detail is print-friendly: use **Print invoice** and the browser's **Save as PDF** option when a PDF copy is needed. Invoice and InvoiceItem records are read-only in Django admin and have no edit or delete workflow.

## Dashboard and reports

The authenticated Dashboard and unified Reports page provide read-only business metrics for Today, the last 7 days, or the last 30 days. Sales revenue always comes from immutable Sale totals; Invoice totals are documents and are never counted as additional revenue.

Reports cover Sales performance, current inventory health, period inventory movement, Customer activity, and Invoice issuance coverage. Daily Sales revenue and the top five Products by historical Sales revenue use Chart.js, while all underlying figures remain available in HTML when charts are unavailable.

Sales and Inventory Movement CSV exports use the same local-calendar period and authorization rules as the reports. Staff exports exclude movements for inactive Products, and user-controlled text is protected against spreadsheet formula injection.

## Verification

```powershell
python -m pip check
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

Generated static output is written to `staticfiles/` and is not committed.

## Production readiness

Production uses Gunicorn on Linux, WhiteNoise compressed manifest static files, secure environment-controlled Django settings, PostgreSQL health checks, and GitHub Actions with a real PostgreSQL service. The public readiness endpoint is `/health/`.

See [Production deployment and recovery](docs/production-deployment.md) for required environment variables, HTTPS and trusted-proxy verification, build and migration commands, smoke testing, backups, restore drills, and rollback guidance. Verify hosting-provider pricing, regions, limits, backup features, and proxy behavior immediately before deploying.

Docker is intentionally outside the current project scope.

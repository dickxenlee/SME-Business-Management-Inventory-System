# Production deployment and recovery

This runbook prepares SME Manager for a Linux application platform with managed PostgreSQL. Railway is the recommended initial target and Render is a reasonable fallback. Verify each provider's current pricing, regions, PostgreSQL limits, backup features, proxy behavior, and deployment commands immediately before deploying; those details can change.

## Architecture

```text
Browser -> trusted HTTPS platform proxy -> Gunicorn -> Django + WhiteNoise
                                                    -> PostgreSQL
GitHub -> GitHub Actions PostgreSQL tests -> platform deployment
```

The application remains PostgreSQL-only. WhiteNoise serves versioned static assets from the application process. Gunicorn runs the synchronous WSGI application on Linux.

## Prerequisites

- A Linux Python 3.11 runtime.
- A managed PostgreSQL database in the same region as the application where possible.
- A production database role that owns or can migrate the application schema but is not a superuser and does not have `CREATEDB`.
- Access to configure private environment variables and the platform health check.
- A verified database backup before upgrading an existing deployment.

## Required environment variables

Set these in the hosting platform's secret-variable interface. Never commit real values to Git.

| Variable | Production requirement |
|---|---|
| `DJANGO_ENVIRONMENT` | `production` |
| `DJANGO_SECRET_KEY` | Unique random value of at least 50 characters; never reuse the repository example |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated exact host names without schemes or wildcards |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated exact HTTPS origins, such as `https://inventory.example.com` |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | Keep `False` until the platform is confirmed to overwrite `X-Forwarded-Proto`; then set `True` |
| `DJANGO_SECURE_HSTS_SECONDS` | Start at `0`; use `3600` only after HTTPS verification, then consider a longer value after stable operation |
| `DJANGO_LOG_LEVEL` | Normally `INFO` |
| `DJANGO_AXES_ENABLED` | Keep `True`; only set `False` to diagnose a lockout problem |
| `DJANGO_AXES_FAILURE_LIMIT` | Failed sign-ins before lockout, normally `5` |
| `DJANGO_AXES_COOLOFF_MINUTES` | Lockout duration in minutes, normally `15` |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | Least-privileged application role |
| `DB_PASSWORD` | Private database password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port, normally `5432` |
| `DB_SSLMODE` | Required secure mode: `require`, `verify-ca`, or `verify-full`; prefer `verify-full` when certificates and host verification are configured |
| `DB_CONNECT_TIMEOUT` | Initial value `5` |
| `DB_CONN_MAX_AGE` | Initial value `60`; reduce it if database connection limits require it |
| `INVOICE_SELLER_NAME` | Real legal or trading name shown on newly issued Invoices |
| `INVOICE_SELLER_ADDRESS` | Real seller address shown on newly issued Invoices |

`DEBUG` is always forced off in production. Production startup rejects missing or placeholder secrets, missing hosts or origins, wildcard hosts, insecure CSRF origins, and invalid Boolean or numeric configuration.

### Generate the secret key

Generate it locally and copy only the output into the platform's private settings:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Do not paste the generated value into documentation, issue trackers, CI configuration, or Git.

## HTTPS and trusted proxy verification

The application does not trust `X-Forwarded-Proto` by default. Before setting `DJANGO_TRUST_PROXY_SSL_HEADER=True`, confirm from the platform's current documentation that its edge proxy removes any client-supplied value and sets the header from the real connection. Incorrect trust can let a client influence Django's secure-request detection.

After deployment:

1. Confirm the public URL uses a valid HTTPS certificate.
2. Confirm an HTTP request redirects to HTTPS once.
3. Confirm HTTPS does not enter a redirect loop.
4. Confirm login and POST logout work through HTTPS.
5. Confirm session and CSRF cookies include the `Secure` attribute.

Keep HSTS at `0` for the initial deployment. After HTTPS and redirect behavior are verified, set it to `3600`. Consider a longer value such as `31536000` only after stable operation. Phase 9 intentionally leaves HSTS preload and include-subdomains disabled.

## Build, migrate, and start

Use these logical platform commands. Adapt command syntax only as required by the chosen provider.

Build:

```sh
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Pre-deploy, run exactly once per release rather than in every web process:

```sh
python manage.py migrate
```

Start:

```sh
gunicorn sme_manager.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile - --error-logfile - --access-logformat '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
```

The access-log format records the request path but deliberately omits query strings and referrers, which can contain Customer search information. Do not use `python manage.py runserver` in production. Review platform and PostgreSQL connection metrics before raising the worker count.

Configure the platform health probe for:

```text
GET /health/
```

The endpoint returns HTTP 200 only when Django can perform a minimal PostgreSQL query. It returns a generic HTTP 503 response on database failure and never includes connection details.

`/health/` is the only path listed in `SECURE_REDIRECT_EXEMPT`, so a probe that requests it over plain HTTP receives the status response instead of an HTTPS redirect. Every other path is still redirected to HTTPS in production, and that redirect is not environment-controlled. Do not widen this exemption to make a probe pass.

## First deployment

1. Confirm GitHub Actions is green.
2. Review the pending migrations and take a backup if replacing an existing deployment.
3. Configure all environment variables.
4. Deploy using the build, pre-deploy, and start commands above.
5. Wait for `/health/` to return HTTP 200.
6. Create the first administrator manually:

   ```sh
   python manage.py createsuperuser
   ```

7. Do not automate or commit administrator credentials.

## Smoke test

Verify through the public HTTPS URL:

- HTTP redirects to HTTPS without a loop.
- `/health/` returns `{"status":"ok"}` and `Cache-Control: no-store`.
- Bootstrap styling, custom CSS, and charts load.
- Admin and Staff can log in and POST logout works.
- Staff cannot enter Django admin or perform Admin-only operations.
- Dashboard and Reports render for each period.
- Product, Inventory, Customer, Sales, and Invoice read flows work.
- An unknown URL shows the custom 404 page without diagnostics.
- A safe CSV export downloads correctly.
- Logs contain useful request errors but no passwords, cookies, secrets, request bodies, or unnecessary Customer details.

## PostgreSQL backup

Provider-managed backups are useful, but retain portable PostgreSQL dumps according to the business retention policy. Store backups in restricted, encrypted storage outside the repository.

Use a PostgreSQL password file or another non-logged credential mechanism. Do not put a password directly on the command line.

```powershell
New-Item -ItemType Directory -Force backups
pg_dump --host <host> --port 5432 --username <user> --format custom --no-owner --file "backups\sme-manager-YYYYMMDD-HHmm.dump" <database>
Get-FileHash -Algorithm SHA256 "backups\sme-manager-YYYYMMDD-HHmm.dump"
```

Record the timestamp, source database, PostgreSQL client version, file size, and checksum in the protected backup register. The `backups/`, `*.dump`, and `*.backup` patterns are ignored by Git.

## Restore validation

Never restore over the live production database as a test. Use a separate empty validation database and credentials authorized for that isolated environment.

```powershell
pg_restore --list "backups\sme-manager-YYYYMMDD-HHmm.dump"
createdb --host <validation-host> --port 5432 --username <validation-admin> sme_manager_restore_test
pg_restore --host <validation-host> --port 5432 --username <validation-admin> --no-owner --exit-on-error --dbname sme_manager_restore_test "backups\sme-manager-YYYYMMDD-HHmm.dump"
```

Before running `pg_restore`, compare the dump's current checksum with the value recorded when the backup was created:

```powershell
$expectedChecksum = Read-Host "Recorded SHA-256 checksum"
$actualChecksum = (Get-FileHash -Algorithm SHA256 "backups\sme-manager-YYYYMMDD-HHmm.dump").Hash
if ($actualChecksum -ne $expectedChecksum) { throw "Backup checksum verification failed; restore stopped." }
```

Stop immediately if the values differ. Run `pg_restore --list`, database creation, and restoration only after the checksum matches.

Point a temporary application instance at the restored database and verify:

```powershell
python manage.py showmigrations
python manage.py check
```

Then verify representative record counts, administrator login, role boundaries, Product stock balances, StockMovement chains, immutable Sales snapshots, and Invoice detail. Delete the validation database only after the results are recorded. Schedule periodic restore drills; an untested backup is not a verified recovery path.

## Rollback and incident considerations

Rollback the application release when health checks repeatedly fail, login is unavailable, static assets are missing, sustained HTTP 500 responses occur, or business-record integrity is at risk.

1. Stop new deployment traffic if the platform supports it.
2. Preserve logs and take a new database backup when safe.
3. Roll back to the previous application release.
4. Recheck `/health/`, authentication, static assets, and business read paths.
5. Investigate and forward-fix the migration or data issue.

An application rollback does not reverse database migrations or data changes. Prefer backward-compatible migrations. Never run a destructive reverse migration or restore a backup over production without separately reviewing the affected data and explicitly authorizing the operation.

## Platform selection reminder

Railway is the initial recommendation because it can provide managed PostgreSQL, GitHub-based deployment, health checks, pre-deploy commands, and centralized logs. Render is the documented fallback. Before real deployment, verify the selected platform's current region availability, pricing, resource and database limits, backup/retention behavior, proxy-header guarantees, and rollback semantics. No provider-specific configuration file is committed in Phase 9.

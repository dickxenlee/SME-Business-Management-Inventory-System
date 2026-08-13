# Project Foundation Design

## Scope

Create only the foundation for an SME business management system. The project package is `sme_manager`, and the only custom Django app is `core`. Product, inventory, customer, sales, invoice, reports, REST API, and Docker functionality are excluded.

## Architecture

Use a conventional Django project with one settings module. The `core` app owns the placeholder home page and its URL configuration. Project-level `templates/` and `static/` directories provide a reusable Bootstrap layout and a small application stylesheet.

## Configuration

Use Django 5.2 LTS with Psycopg 3 and PostgreSQL exclusively. `python-dotenv` loads local values from an ignored `.env` file. `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are mandatory; host and port default to `localhost` and `5432`. PostgreSQL connection attempts time out after five seconds so unavailable local services fail promptly. No credential or secret is committed, and `.env.example` contains placeholders only.

## Behavior

The root URL renders a dashboard placeholder using `templates/core/home.html`, extending `templates/base.html`. The base template loads Bootstrap from its official CDN, renders reusable navigation, and includes the project stylesheet. Unknown URLs retain Django's standard 404 behavior.

## Verification

Foundation tests use `SimpleTestCase` so page behavior can be verified independently of database availability. Full verification also includes Django checks, migration drift detection, PostgreSQL migration, test execution, static collection, Git-ignore validation, and manual browser inspection. PostgreSQL verification must remain blocked if no server is available; SQLite is never used as a fallback.

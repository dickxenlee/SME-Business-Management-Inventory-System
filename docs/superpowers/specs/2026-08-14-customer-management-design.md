# Customer Management Design

## Scope

Phase 5 adds server-rendered Customer list, detail, create, edit, soft deactivation, search, pagination, and Django-admin visibility. It does not add Sales, Invoice, Reports, REST API, Docker, deployment, customer codes, contact deduplication, or snapshot fields.

## Data model

Create a dedicated `customers` app with a `Customer` model containing `name`, optional `phone`, optional `email`, optional `address`, `is_active`, `created_at`, and `updated_at`. Use the database primary key as the identifier and order Customers by name then primary key. No contact field is unique.

Name is trimmed and required. Email uses Django's `EmailField`. Phone accepts digits, spaces, hyphens, parentheses, and an optional leading `+`, with 7–15 digits and a maximum stored length of 20 characters. Contact values remain close to user input; no phone-number package or aggressive normalization is added.

## Authorization and visibility

Superusers may list and view active/inactive Customers, create Customers, edit active/inactive Customers, and deactivate active Customers. Existing Staff group members may list/view active Customers, create Customers, and edit active Customers. Staff receive HTTP 404 for inactive detail/edit URLs and HTTP 403 for deactivation. Authenticated users outside these roles receive HTTP 403; anonymous users are redirected to login.

Deactivation is POST-only, CSRF-protected, idempotent, and sets `is_active=False`. Customer rows cannot be physically deleted through normal UI or Django admin.

## UI and querying

Use class-based views, a `CustomerForm`, the shared Bootstrap base template, and `/customers/` URLs matching Product conventions. Search parameter `q` matches name, phone, or email through Django ORM `icontains` queries. Pagination uses 20 rows and preserves search. Staff active filtering occurs before search.

## Future Sales compatibility

Phase 6 can add a nullable, blank Customer foreign key on Sale with `on_delete=PROTECT` so null represents walk-in sales. Deactivated Customers remain available to historical Sales but should be excluded from new-sale selection. Customer name/address snapshots belong in the future Sales/Invoice design, not Phase 5.

## Testing

Tests cover model and form validation, optional and duplicate contact values, role permissions, inactive visibility, create/edit/deactivate behavior, POST and CSRF enforcement, row preservation, search and 20-row pagination, Django-admin deletion prevention, and the complete Phase 1–4 regression suite.

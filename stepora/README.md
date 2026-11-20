# Stepora.ro — Ecommerce application

Custom Romanian footwear ecommerce platform. This project is isolated under `stepora/` in the existing `breburadu/breburadu` repository.

**Baseline:** Stepora v0.9.1 reference package (PHP, MariaDB, Nginx/PHP-FPM).

**Source import:** The complete baseline is available as the previously generated `stepora_github_ready_v0_9_1.zip`. The full application source tree must be imported into this folder; this README does not mean the application has been uploaded.

See [PROJECT_INFO.md](PROJECT_INFO.md) for non-application project requirements, environment, decisions, history, and security/deployment policies.

Repository layout after full import:
- `app/`, `config/`, `public/`, `scripts/` — runtime code
- `database/install/full_schema_latest.sql` — consolidated fresh-install SQL
- `database/migrations/` — incremental upgrade history
- `public/assets/branding/stepora-logo.png` — generated logo
- `docs/` — application and integration docs

Do not commit `.env`, secrets, production SQL dumps, `storage/` runtime data, or uploaded customer files. Deployments must preserve live `.env`, `storage/`, and `public/uploads/`.

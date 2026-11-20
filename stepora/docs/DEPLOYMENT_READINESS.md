# Stepora deployment readiness (v0.9.1)

**Status: NOT YET VERIFIED FOR PRODUCTION.** The current GitHub folder is incomplete until the full PHP app, migrations, SQL, assets and demo SVGs are imported. Do not deploy the current repository folder as an ecommerce application.

## Known blocking findings
1. The v0.9.1 consolidated SQL and initial migration contain an ambiguous `ON DUPLICATE KEY UPDATE sku = sku` in the demo-product seed. Replace with `sku = products.sku` before fresh install. The previously reported migration 002 ambiguity has already been fixed separately.
2. The previously prepared import script excluded `public/uploads/` while the demonstration SQL references **20 SVG images under `public/uploads/products/demo/`**. Import demo assets intentionally, but never import production/customer uploads.
3. A GitHub folder with only README and project metadata is not deployable. Import all application files first.
4. The actual production server database, Nginx config, PHP 8.5 extensions, mail flow, order creation, stock reservation and admin workflows have not been end-to-end tested in this review.

## Deployment checklist
- Import and review complete source under `stepora/` only. Verify `composer.json`, `app/bootstrap.php`, `public/index.php`, `database/install/full_schema_latest.sql`, logo PNG and demo SVGs.
- Run `bash stepora/scripts/preflight-deploy.sh` on a VM with PHP-FPM/CLI extensions installed; pass all checks.
- Back up the existing DB and existing `.env`, `storage/` and `public/uploads/` before updating.
- Deploy using safe `rsync -av --delete --exclude='.env' --exclude='storage/' --exclude='public/uploads/' SOURCE/ TARGET/` and verify correct trailing slashes. On a **fresh** install, populate demo SVGs separately from packaged source.
- Use `.env.production.template` only to initialize a **new** `.env`, never overwrite an existing one. Configure a dedicated non-root MariaDB user; never put production secrets in Git.
- Fresh DB: run consolidated SQL **only on an empty database**, after fixing seed ambiguity. Existing DB: apply only missing incremental migrations, never the full seed file blindly.
- Configure Nginx document root `/var/www/stepora.ro/public`, route fallback `/index.php?$query_string`, and match installed PHP-FPM socket (reported `php8.5-fpm.sock`). Verify HTTPS.
- Change default seeded admin password before exposure; verify admin login, standalone 2FA, logout CSRF, role permissions and trusted IP settings.
- Smoke-test homepage, products/images, register/email confirmation, optional SMS, cart, guest/registered checkout, order status, stock reservation/release, and admin deletion handling.
- Keep PayU.ro, Sameday/easybox and SMSAPI.ro **disabled** until authenticated sandbox and production callbacks are validated. Audit GDPR, cookie consent and privacy/legal content before opening store.

## Environment note
The local source-review environment does not have MariaDB, `pdo_mysql`, or `mbstring`; it can run PHP syntax checks but not database/import or end-to-end PHP application tests. Missing local extensions are not proof they are missing on the user's VM.

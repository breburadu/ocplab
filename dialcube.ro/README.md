# Dialcube.ro — deployment and development

PHP 8.1+ / MariaDB 10.5+ or MySQL 8+ presentation site. Site source is in `httpdocs/`; the only intended PHP entry point is `httpdocs/index.php`. The repository's other projects remain independent.

## First deployment

1. Install Nginx (or Apache), PHP-FPM, extensions `mysqli`, `fileinfo`, `openssl`, `mbstring`, `rsync`, and Composer.
2. Provision a MariaDB/MySQL database and restricted database user. Import `database/schema.sql` **only for a new, empty database**. This schema was inferred from PHP queries and contains **no production content**. For an existing site, restore its real database dump and check schema compatibility.
3. Set `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `BASE_URL`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_PORT`, `SMTP_FROM`, and optionally `CONTACT_TO` as PHP-FPM environment variables. `.env.example` is a reference and is **not** automatically loaded. Ensure PHP-FPM's `clear_env` configuration permits the required variables.
4. Run `bash scripts/deploy.sh /var/www/dialcube.ro/httpdocs` on the application host. Set the web document root to the resulting `httpdocs` directory. See `docs/nginx-dialcube.conf.example`; update certificate paths and the PHP-FPM socket before enabling.
5. Run Composer on the server (`composer install --no-dev --prefer-dist --optimize-autoloader`) to install PHPMailer. Check SMTP TLS, DNS and firewall connectivity.
6. For a new database, from the project root set `ADMIN_INITIAL_PASSWORD` securely and run `php scripts/create_admin.php youradmin`; then clear that environment variable.
7. Enable TLS, confirm filesystem ownership, and test all routes and admin functions before directing production traffic. Do not expose `scripts/`, `database/`, or `docs/` as web-served paths.

## Update behavior

The deploy script backs up deployed code and uses `rsync` without `--delete`. It preserves an existing `.env`, `uploads/`, and `storage/`; it does not overwrite live `vendor/` when copying. Composer may update `vendor/` afterwards, so back it up separately before major dependency upgrades. **The script does not deploy or alter production database data.**

## Security and limitations

The original uploaded archive contained embedded database and SMTP secrets: rotate both before deploying. Code revisions introduce session/CSRF validation, controlled upload MIME types and verified SMTP TLS. Public-facing deployment should undergo integration testing against the intended database, SMTP server and Nginx/PHP-FPM stack. There is no real production database snapshot or server access in this repository.

See `docs/PROJECT_INFO.md` for source archive inventory and non-development notes.

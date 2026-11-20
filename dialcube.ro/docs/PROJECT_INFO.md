# Dialcube project information

Source: `dialcube (1).zip`, extracted from `httpdocs/` (archive dates July 2025).

## Non-development / deployment artifacts
- `.well-known/acme-challenge/.htaccess`: ACME hosting challenge configuration, retained in source tree.
- `robots.txt` and `sitemap.xml`: search engine deployment assets, retained in source tree.
- `PHPMailer/` and `vendor/`: bundled third-party dependencies from the original archive, excluded from version control; restore using Composer where supported.
- `wefjwefjweoipheofw_testemail.php`: ad hoc email test endpoint, excluded from deployment repository to reduce exposure.
- Original archive should be retained separately as a private backup, **not** committed to GitHub because it contains credentials.

## Production configuration
Original `config.php` and `config/email.php` contained embedded credentials. Repository copies use `DB_PASS` and `SMTP_PASSWORD` environment variables. Set these in PHP-FPM / web server environment securely. A `.env` file is NOT automatically loaded by the application.

## Security and migration
Rotate database and SMTP credentials exposed in the original archive. Review other application code for authentication, CSRF, SQL injection and email handling before production deployment. Confirm Composer dependency compatibility before removing bundled PHPMailer in production.

## Repository layout
`httpdocs/` is the website document root; `docs/` contains non-development notes and archive inventory; root contains repository metadata and environment templates.

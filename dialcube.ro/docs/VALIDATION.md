# Validation status — 20 November 2026

## Completed
- Local ZIP contents verified with `unzip -t`.
- Local PHP source files passed `php -l` on PHP 8.4 CLI.
- `scripts/deploy.sh` passed `bash -n`.
- GitHub source tree contains the application pages, handlers, SQL schema and deployment scripts.
- A GitHub Actions CI workflow has been committed to test PHP 8.3 + MariaDB 10.11.

## Not yet verified
- Whether GitHub Actions has completed successfully; do not assume green CI.
- Live PHP-FPM/Nginx integration, DNS/TLS, SMTP sending and database contents.
- Production database migrations: the schema is inferred from code, not an existing SQL backup.
- PHP runtime integration locally, because `mysqli` was not installed in the local PHP CLI.
- Security review against production traffic.

This repository is ready for a controlled **staging deployment**, not an already tested live production rollout.

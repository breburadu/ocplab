# Conference deployment runbook

## Readiness status
This is an archived event web application, with configured date **25 January 2025**. Deployment does not mean opening registration; it will remain closed until an authorized future event date is set.

## Files and layout
- Git: `projects/healingfriends/sites/conference.healingfriends.ro/public/`
- Server site: `/var/www/healingfriends/conference/public`
- Private registrant data: `/var/lib/healingfriends/conference` (never under webroot)
- Public images `event.jpg` and `fav.webp` need to be copied from original uploads, not reconstructed.
- Missing source documents `gdprro` and `event_price.txt` must be provided and reviewed. Do not improvise legal notices or pricing.
- Mail template `email.txt` contains `{{PAYMENT_IBAN}}`; replace with verified account details on the deployment target, not in Git.
- Original registration SMTP credential was visible in the source. **Rotate it before any deployment.**

## Prerequisites
Debian/Ubuntu with Nginx, PHP-FPM, PHP CLI extensions mbstring and openssl, Composer, DNS and a valid TLS certificate. Have a dedicated FPM pool or environment injection for HF_* values. Check FPM `clear_env` and configure `env[HF_...]` in the dedicated pool if required. Do not expose these through Nginx public root.

## Initial deployment (example, review paths and usernames)
1. Copy the `public/` directory into `/var/www/healingfriends/conference/public/` while preserving any valid server-side content.
2. Install PHP libraries from the application public directory: `composer install --no-dev --prefer-dist --no-interaction --optimize-autoloader`.
3. Provision `/var/lib/healingfriends/conference`, owned and writable only by the PHP-FPM service account. Keep data out of Git, backups protected.
4. Add SMTP variables using the server's secret mechanism / dedicated PHP-FPM pool (use `.env.example` as a reference only, no secret file in the webroot).
5. Place original images in public root, supply approved Romanian GDPR notice and verified price, and replace the payment placeholder in the deployed mail template.
6. Review `deployment/nginx/conference.healingfriends.ro.conf`. Replace `YOUR_PHP_FPM_SOCKET`; ensure certificates exist before enabling TLS server. Enable configuration and run `nginx -t` before reload.
7. Run `HF_STORAGE_DIR=/var/lib/healingfriends/conference sh install-scripts/conference/preflight.sh /var/www/healingfriends/conference` with the same HF_* environment as PHP-FPM.
8. Smoke test landing page, images, popups, response headers, access restrictions on `email.txt`, `vendor/`, `.env`, and HTTPS redirect. Test form delivery in staging with an approved future date and test SMTP account, never with live participant data. Restore event date afterward.

## Operational notes
- Never overwrite existing `.env`, runtime registration storage or user uploads on deployments.
- Do not deploy `registrants.txt` from the old upload. Any migration of existing participants must be handled separately, with authorization and secure data handling.
- The application currently sends a confirmation email before appending registrant data. Production readiness requires successful SMTP testing and legal/privacy review.
- Back up private data securely, determine retention and deletion policy, monitor errors and throttling.

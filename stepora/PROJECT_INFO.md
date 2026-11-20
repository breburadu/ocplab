# Stepora.ro — Project information (non-application)

This document preserves the business requirements, architecture decisions, and deployment history. It is **not runtime application logic**.

## Scope and technology
- Romanian niche shoe ecommerce site: **stepora.ro**
- Custom PHP + MariaDB application, Nginx, PHP-FPM (PHP 8.5 reported on VM); server provisioned through hf-stack.sh with mail already operating.
- Reference source is v0.9.1 full package. The repository source snapshot is **not guaranteed to reflect later edits on the live VM**.

## Functional requirements
- Product-focused responsive modern storefront, product descriptions/images, variants/sizes, stock, cart, guest checkout, user accounts, order status/history.
- Admin-driven product create/edit/delete, inventory, orders, customers/admin users and password changes, roles, editable logo/theme/SEO/legal content and feature switches.
- Stock controlled locally or through versioned authenticated ERP/stock API; audit movements, reserve on order, release on cancellation; guard against overselling.
- Account email confirmation, optional SMS/phone confirmation; if SMS enabled, require verification for new accounts and guest orders according to settings.
- SMSAPI.ro provider hooks, PayU.ro payment readiness, Sameday courier/easybox readiness; verify live integrations with actual merchant contracts.
- Optional email-code admin 2FA, trusted-IP bypass allowlist, maintenance mode with trusted-IP exceptions, per-IP and global SMS/email rate limits, editable blacklist, contextual admin help.
- Admin login and 2FA pages must be standalone, without protected admin menus.
- Ads/analytics integrations must be backend-controlled with generic injection zones, consent gating and editable GDPR/cookie/account/data-sharing text.

## Known fixes from development
- Nginx root must be `/var/www/stepora.ro/public` with front-controller rewrites.
- SQL migration 002 ambiguous `sku=sku` duplicate update corrected by qualifying target.
- Cookie banner `[hidden]` style must override flex display.
- Undefined `csrf_field()` caused PHP fatal; forms use supported `Stepora\\Core\\Csrf::token()` and verify POST tokens.
- Standalone admin login requires avoiding `view('admin/login', ..., 'admin')`; controller must render without authenticated layout. Same for email-code 2FA.
- When SMS and phone-required settings are off, phone verification button must not appear.
- Missing/deleted production `.env` caused PDO to default to root and HTTP 500. Do not replace `.env`.

## Release and deployment rules
- **Do not generate downloadable archives automatically**; only when explicitly requested.
- Every requested release must be a complete current source package with one consolidated *fresh-install* SQL file and any necessary existing-db upgrade procedure.
- Keep `.env.example` and `.env.production.template`; never commit live credentials. Preserve live `.env`, `storage/`, and `public/uploads/` on every deployment.
- Use safe rsync excludes, test Nginx/PHP and back up existing database before migrations.
- No real passwords, API keys, personal customer information, full production dumps, or private VM details in GitHub.

## Logo
Generated minimalist navy/purple stylized S with sneaker silhouette; expected packaged file `public/assets/branding/stepora-logo.png` (source 1254×1254). Web UI renders branding roughly 36px high on storefront and 44px square on admin. Ensure the logo asset is imported along with the application.

## Production readiness
Integration-ready does not equal tested live. Verify account/email/SMS, checkout, inventory, payment webhooks, easybox selection, authorization, 2FA, data deletion/retention, GDPR and consent, CSRF, rate limiting, backups, and upload handling before public production sales.

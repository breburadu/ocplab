#!/bin/sh
set -eu
APP="${1:-/var/www/healingfriends/conference}"
PUBLIC="$APP/public"
STORAGE="${HF_STORAGE_DIR:-/var/lib/healingfriends/conference}"
FAILED=0
ok(){ printf 'OK: %s\n' "$1"; }
fail(){ printf 'FAIL: %s\n' "$1"; FAILED=1; }
command -v php >/dev/null 2>&1 && ok "php executable" || fail "php executable"
for f in index.php register.php composer.json composer.lock title.txt content.txt eventmoto.txt event_date.txt disclaimerro disclaimeren gdpren gdprro email.txt event_price.txt event.jpg fav.webp vendor/autoload.php; do
    if [ -s "$PUBLIC/$f" ]; then ok "$f"; else fail "missing/empty $f"; fi
done
if command -v php >/dev/null 2>&1; then
    php -l "$PUBLIC/index.php" || FAILED=1
    php -l "$PUBLIC/register.php" || FAILED=1
    for ext in mbstring openssl; do
        php -m | grep -iq "^$ext$" && ok "PHP $ext" || fail "PHP $ext extension"
    done
fi
[ -d "$STORAGE" ] && [ -w "$STORAGE" ] && ok "private writable storage" || fail "private writable storage: $STORAGE"
case "$STORAGE" in "$PUBLIC"|"$PUBLIC"/*) fail "storage must be outside public webroot" ;; esac
if [ -f "$PUBLIC/email.txt" ] && grep -q '{{PAYMENT_IBAN}}' "$PUBLIC/email.txt"; then fail "payment account placeholder not configured"; fi
event="$(cat "$PUBLIC/event_date.txt" 2>/dev/null || true)"
case "$event" in
  ????????) ok "event date has eight characters; verify day and date" ;;
  *) fail "event_date.txt must contain DDMMYYYY" ;;
esac
[ -n "${HF_SMTP_PASSWORD:-}" ] && [ -n "${HF_SMTP_USERNAME:-}" ] && [ -n "${HF_SMTP_HOST:-}" ] && ok "SMTP variables set" || fail "SMTP environment missing"
if [ "$FAILED" -eq 0 ]; then
  echo "Local prerequisite checks passed. Still verify DNS, TLS, PHP-FPM, SMTP delivery, public HTTP access and privacy compliance."
else
  echo "Deployment blocked: address FAIL results before activation."
fi
exit "$FAILED"

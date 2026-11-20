#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
errors=0
for file in public/index.php app/bootstrap.php database/install/full_schema_latest.sql .env.production.template public/assets/branding/stepora-logo.png; do
  if [[ -f "$ROOT/$file" ]]; then echo "PASS: $file"; else echo "FAIL missing: $file"; errors=$((errors+1)); fi
done
demo_count=$(find "$ROOT/public/uploads/products/demo" -type f -name '*.svg' 2>/dev/null | wc -l)
if [[ "$demo_count" -lt 20 ]]; then echo "FAIL: only $demo_count/20 demo images"; errors=$((errors+1)); fi
if command -v php >/dev/null; then
  while IFS= read -r -d '' file; do
    if ! php -l "$file" >/dev/null 2>&1; then echo "FAIL PHP syntax: $file"; errors=$((errors+1)); fi
  done < <(find "$ROOT/app" "$ROOT/public" -name '*.php' -type f -print0)
  for ext in pdo_mysql mbstring json; do
    if ! php -m | grep -iq "^$ext$"; then echo "FAIL missing PHP extension: $ext"; errors=$((errors+1)); fi
  done
else echo 'FAIL: PHP executable missing'; errors=$((errors+1)); fi
if grep -Rqs 'csrf_field()' "$ROOT/app/Views"; then echo 'FAIL undefined csrf_field helper'; errors=$((errors+1)); fi
if grep -Eq 'ON DUPLICATE KEY UPDATE sku[[:space:]]*=[[:space:]]*sku[;[:space:]]' "$ROOT/database/install/full_schema_latest.sql"; then echo 'FAIL ambiguous SQL duplicate-key expression'; errors=$((errors+1)); fi
if [[ -f "$ROOT/.env" ]]; then
  if grep -Eq '^DB_USERNAME=root$|^DB_PASSWORD=(change_me|)$' "$ROOT/.env"; then echo 'FAIL: default/root DB connection'; errors=$((errors+1)); fi
else echo 'NOTE: .env intentionally absent in Git; create on server and rerun'; fi
((errors==0)) || { echo "Preflight failed: $errors issues"; exit 1; }
echo 'Static preflight passed. Database, HTTPS, mail, SMS, courier, payment and checkout tests are separate.'

#!/usr/bin/env bash
set -Eeuo pipefail
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../httpdocs" && pwd)"
TARGET_DIR="${1:-/var/www/dialcube.ro/httpdocs}"
[[ -f "$SOURCE_DIR/index.php" ]] || { echo 'Missing application sources' >&2; exit 1; }
command -v rsync >/dev/null || { echo 'Install rsync' >&2; exit 1; }
command -v php >/dev/null || { echo 'Install PHP' >&2; exit 1; }
install -d -m 0755 "$TARGET_DIR"
if [[ -f "$TARGET_DIR/index.php" ]]; then
    SNAPSHOT="$(dirname "$TARGET_DIR")/backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$SNAPSHOT"
    rsync -a --exclude='.env' --exclude='uploads/' --exclude='storage/' "$TARGET_DIR/" "$SNAPSHOT/"
    echo "Backup: $SNAPSHOT"
fi
rsync -av --exclude='.env' --exclude='.env.*' --exclude='uploads/' --exclude='storage/' \
 --exclude='vendor/' --exclude='PHPMailer/' "$SOURCE_DIR/" "$TARGET_DIR/"
install -d -m 0750 "$TARGET_DIR/uploads" "$TARGET_DIR/storage"
if [[ -f "$SOURCE_DIR/uploads/.htaccess" ]]; then cp "$SOURCE_DIR/uploads/.htaccess" "$TARGET_DIR/uploads/.htaccess"; fi
if command -v composer >/dev/null; then
    (cd "$TARGET_DIR" && COMPOSER_ALLOW_SUPERUSER=1 composer install --no-dev --prefer-dist --optimize-autoloader --no-interaction)
else
    echo 'WARNING: Composer must be installed before serving the contact form' >&2
fi
find "$TARGET_DIR" -type f -name '*.php' -not -path '*/vendor/*' -print0 | xargs -0 -n1 php -l >/dev/null
echo "Files deployed to $TARGET_DIR. Configure PHP-FPM environment and database separately."

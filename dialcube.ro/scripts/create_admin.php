<?php
// CLI only: ADMIN_INITIAL_PASSWORD=... php scripts/create_admin.php USERNAME
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
$username = $argv[1] ?? '';
if (!preg_match('/^[A-Za-z0-9_.-]{3,100}$/', $username)) {
    fwrite(STDERR, "Usage: php scripts/create_admin.php USERNAME\n"); exit(1);
}
$password = getenv('ADMIN_INITIAL_PASSWORD');
if (!$password || strlen($password) < 14) {
    fwrite(STDERR, "Set ADMIN_INITIAL_PASSWORD (14+ chars) in environment\n"); exit(1);
}
$db = new mysqli(getenv('DB_HOST') ?: 'localhost', getenv('DB_USER') ?: '', getenv('DB_PASS') ?: '', getenv('DB_NAME') ?: '');
$hash = password_hash($password, PASSWORD_DEFAULT);
$stmt = $db->prepare("INSERT INTO admins (username,password,access_level) VALUES (?,?,'admin') ON DUPLICATE KEY UPDATE password=VALUES(password)");
$stmt->bind_param('ss', $username, $hash);
$stmt->execute();
echo "Admin account created/updated. Clear ADMIN_INITIAL_PASSWORD.\n";

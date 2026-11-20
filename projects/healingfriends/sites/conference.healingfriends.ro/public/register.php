<?php
declare(strict_types=1);
session_start();
header('Content-Type: text/html; charset=UTF-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function redirectMessage(string $message): never {
    $_SESSION['flash_message'] = $message;
    header('Location: index.php', true, 303);
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    exit('Method not allowed');
}
if (empty($_SESSION['csrf_token']) || !hash_equals($_SESSION['csrf_token'], (string)($_POST['csrf_token'] ?? ''))) {
    http_response_code(403);
    exit('Invalid form token');
}
unset($_SESSION['csrf_token']);
$name = trim((string)($_POST['name'] ?? ''));
$email = trim((string)($_POST['email'] ?? ''));
$telephone = trim((string)($_POST['telephone'] ?? ''));
if (mb_strlen($name) < 2 || mb_strlen($name) > 120 ||
    !filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 254 ||
    !preg_match('/^[+0-9() .-]{6,30}$/', $telephone)) {
    redirectMessage('Date de contact invalide. Verificați câmpurile și reîncercați.');
}
$eventDate = DateTimeImmutable::createFromFormat('!dmY', trim((string)@file_get_contents(__DIR__ . '/event_date.txt')), new DateTimeZone('Europe/Bucharest'));
if (!$eventDate) {
    http_response_code(503);
    exit('Event date is not configured');
}
if (new DateTimeImmutable('today', new DateTimeZone('Europe/Bucharest')) > $eventDate) {
    redirectMessage('Înscrierile la acest eveniment s-au încheiat.');
}
$storage = getenv('HF_STORAGE_DIR') ?: dirname(__DIR__) . '/storage';
if (!is_dir($storage) || !is_writable($storage)) {
    error_log('Healing Friends: private storage missing or not writable');
    http_response_code(503);
    exit('Registration is temporarily unavailable');
}
$smtpPassword = getenv('HF_SMTP_PASSWORD');
$smtpUser = getenv('HF_SMTP_USERNAME') ?: '';
$smtpHost = getenv('HF_SMTP_HOST') ?: '';
if (!$smtpPassword || !$smtpUser || !$smtpHost) {
    error_log('Healing Friends: SMTP environment incomplete');
    http_response_code(503);
    exit('Registration is temporarily unavailable');
}
$clientIp = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$rateFile = $storage . '/rate-limit.json';
$rateFp = fopen($rateFile, 'c+');
if (!$rateFp || !flock($rateFp, LOCK_EX)) {
    http_response_code(503);
    exit('Registration is temporarily unavailable');
}
$raw = stream_get_contents($rateFp);
$limits = json_decode($raw ?: '{}', true);
if (!is_array($limits)) $limits = [];
$now = time();
$limits = array_filter($limits, static fn($v) => is_array($v) && (int)($v['since'] ?? 0) > $now - 3600);
$key = hash('sha256', $clientIp);
$entry = $limits[$key] ?? ['since' => $now, 'count' => 0];
if ((int)$entry['count'] >= 3) {
    flock($rateFp, LOCK_UN);
    fclose($rateFp);
    http_response_code(429);
    exit('Prea multe încercări. Reîncercați mai târziu.');
}
$entry['count']++;
$limits[$key] = $entry;
rewind($rateFp);
ftruncate($rateFp, 0);
fwrite($rateFp, json_encode($limits, JSON_THROW_ON_ERROR));
fflush($rateFp);
flock($rateFp, LOCK_UN);
fclose($rateFp);
$registrantsFile = $storage . '/registrants.jsonl';
$registrants = @fopen($registrantsFile, 'c+');
if (!$registrants || !flock($registrants, LOCK_EX)) {
    http_response_code(503);
    exit('Registration is temporarily unavailable');
}
rewind($registrants);
while (($line = fgets($registrants)) !== false) {
    $previous = json_decode($line, true);
    if (is_array($previous) && strcasecmp((string)($previous['email'] ?? ''), $email) === 0) {
        flock($registrants, LOCK_UN);
        fclose($registrants);
        redirectMessage('Această adresă de email este deja înregistrată.');
    }
}
require_once __DIR__ . '/vendor/autoload.php';
$template = (string)@file_get_contents(__DIR__ . '/email.txt');
if (!$template || str_contains($template, '{{PAYMENT_IBAN}}')) {
    flock($registrants, LOCK_UN);
    fclose($registrants);
    error_log('Healing Friends: email template or payment details not configured');
    http_response_code(503);
    exit('Registration is temporarily unavailable');
}
$body = str_replace('{{name}}', $name, $template);
try {
    $mail = new PHPMailer\PHPMailer\PHPMailer(true);
    $mail->isSMTP();
    $mail->Host = $smtpHost;
    $mail->SMTPAuth = true;
    $mail->Username = $smtpUser;
    $mail->Password = $smtpPassword;
    $mail->SMTPSecure = PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_STARTTLS;
    $mail->Port = (int)(getenv('HF_SMTP_PORT') ?: 587);
    $mail->CharSet = 'UTF-8';
    $mail->setFrom(getenv('HF_MAIL_FROM') ?: $smtpUser, 'Healing Friends');
    $mail->addAddress($email, $name);
    $mail->addReplyTo(getenv('HF_MAIL_FROM') ?: $smtpUser);
    $mail->Subject = 'Confirmare preînregistrare Healing Friends';
    $mail->Body = $body;
    $mail->send();
} catch (Throwable $e) {
    flock($registrants, LOCK_UN);
    fclose($registrants);
    error_log('Healing Friends SMTP error: ' . $e->getMessage());
    redirectMessage('Mesajul nu a putut fi trimis. Reîncercați mai târziu.');
}
fseek($registrants, 0, SEEK_END);
fwrite($registrants, json_encode(['name' => $name, 'email' => $email, 'telephone' => $telephone, 'created_at' => gmdate('c')], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . "\n");
fflush($registrants);
flock($registrants, LOCK_UN);
fclose($registrants);
redirectMessage('Preînregistrarea a fost transmisă. Verificați emailul pentru detalii.');

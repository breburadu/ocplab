<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/router.php';
// Process the selected page before sending headers, so admin redirects work.
ob_start();
route();
$pageHtml = ob_get_clean();
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Technology services">
  <meta name="robots" content="index, follow">
  <title>Dialcube Tech Site</title>
  <link rel="stylesheet" href="assets/css/style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
<?php include __DIR__ . '/includes/navbar.php'; ?>
<main class="container mt-4">
<?php
echo preg_replace_callback('/<form\b[^>]*method=["\']post["\'][^>]*>/i', function ($match) {
    return $match[0] . '<input type="hidden" name="csrf_token" value="' .
        htmlspecialchars($_SESSION['csrf_token'], ENT_QUOTES) . '">';
}, $pageHtml);
?>
</main>
<?php include __DIR__ . '/includes/footer.php'; ?>
</body>
</html>

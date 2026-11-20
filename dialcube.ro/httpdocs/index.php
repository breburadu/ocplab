<?php


//ini_set('display_errors', 1);
//ini_set('display_startup_errors', 1);
//error_reporting(E_ALL);


require_once 'config.php';
require_once 'router.php';
?>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Tech presentation website">
  <meta name="keywords" content="technology, innovation, services">
  <meta name="robots" content="index, follow">
  <title>Dialcube Tech Site</title>
  <link rel="stylesheet" href="assets/css/style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
  <?php include 'includes/navbar.php'; ?>
  <main class="container mt-4">
    <?php route(); ?>
  </main>
  <?php include 'includes/footer.php'; ?>
</body>
</html>

<nav class="navbar navbar-expand-lg navbar-dark bg-dark"><div class="container-fluid">
<a class="navbar-brand" href="index.php">Dialcube</a>
<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav"><span class="navbar-toggler-icon"></span></button>
<div class="collapse navbar-collapse" id="navbarNav"><ul class="navbar-nav ms-auto">
<li class="nav-item"><a class="nav-link" href="index.php?page=home">Home</a></li>
<li class="nav-item"><a class="nav-link" href="index.php?page=services">Services</a></li>
<li class="nav-item"><a class="nav-link" href="index.php?page=contact">Contact</a></li>
<?php if (!empty($_SESSION['admin_id'])): ?>
<li class="nav-item"><a class="nav-link" href="index.php?page=admin">Admin</a></li>
<li class="nav-item"><a class="nav-link" href="index.php?page=logout">Logout</a></li>
<?php else: ?><li class="nav-item"><a class="nav-link" href="index.php?page=login">Login</a></li><?php endif; ?>
</ul></div></div></nav>
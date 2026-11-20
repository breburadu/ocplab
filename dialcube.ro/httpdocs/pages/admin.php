<?php if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; } ?>
<div class="container"><h2>Admin Dashboard</h2><div class="row g-3">
<?php foreach ([
'manage_categories'=>'Categories','manage_menus'=>'Menus','manage_content'=>'Content',
'manage_seo'=>'SEO','manage_social'=>'Social Links','manage_services'=>'Services',
'manage_messages'=>'Contact Messages','logout'=>'Logout'] as $key=>$label): ?>
<div class="col-md-3"><a class="btn btn-outline-primary w-100" href="index.php?page=<?= $key ?>"><?= htmlspecialchars($label) ?></a></div>
<?php endforeach; ?></div></div>
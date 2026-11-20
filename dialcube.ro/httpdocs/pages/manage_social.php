<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
include_once 'includes/social-handler.php';
?>
<h2>Social Media Links</h2>
<?php if (!empty($message)): ?><p><?= htmlspecialchars($message) ?></p><?php endif; ?>
<form method="POST" class="row g-2">
<div class="col-md-4"><input name="platform" class="form-control" placeholder="Platform" required></div>
<div class="col-md-6"><input type="url" name="url" class="form-control" placeholder="https://..." required></div>
<div class="col-md-2"><button name="update_social" class="btn btn-primary">Update</button></div></form>
<ul class="list-group mt-3"><?php foreach($socials as $link): ?>
<li class="list-group-item"><strong><?= htmlspecialchars($link['platform']) ?></strong> :
<a href="<?= htmlspecialchars($link['url']) ?>" rel="noopener noreferrer" target="_blank"><?= htmlspecialchars($link['url']) ?></a></li>
<?php endforeach; ?></ul>
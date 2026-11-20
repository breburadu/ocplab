<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
include_once 'includes/menus-handler.php';
?>
<h2>Manage Menus</h2><form method="POST" class="row g-2">
<div class="col-md-4"><input class="form-control" name="menu_label" placeholder="Label" required></div>
<div class="col-md-4"><input class="form-control" name="menu_link" placeholder="?page=home" required></div>
<div class="col-md-4"><button name="add_menu" class="btn btn-primary">Add Menu</button></div></form>
<?php if (!empty($message)): ?><p><?= htmlspecialchars($message) ?></p><?php endif; ?>
<table class="table"><thead><tr><th>Label</th><th>Link</th><th>Action</th></tr></thead><tbody>
<?php foreach($menus as $item): ?><tr><td><?= htmlspecialchars($item['label']) ?></td><td><?= htmlspecialchars($item['link']) ?></td>
<td><form method="POST"><input name="delete_id" type="hidden" value="<?= (int)$item['id'] ?>"><button name="delete_menu" class="btn btn-danger btn-sm">Delete</button></form></td></tr>
<?php endforeach; ?></tbody></table>
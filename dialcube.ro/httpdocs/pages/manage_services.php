<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
include_once 'includes/services-handler.php';
?>
<h2>Manage Services</h2><form method="POST">
<input type="hidden" name="service_id" value="<?= (int)($edit['id']??0) ?>">
<div class="mb-2"><input name="service_name" class="form-control" placeholder="Service name" value="<?= htmlspecialchars($edit['name']??'') ?>" required></div>
<div class="mb-2"><select name="category_id" class="form-select" required>
<?php foreach($categories as $cat): ?><option value="<?= (int)$cat['id'] ?>" <?= (int)($edit['category_id']??0)===(int)$cat['id']?'selected':'' ?>><?= htmlspecialchars($cat['name']) ?></option><?php endforeach; ?>
</select></div>
<div class="mb-2"><textarea name="description" class="form-control"><?= htmlspecialchars($edit['description']??'') ?></textarea></div>
<button class="btn btn-success" name="save_service">Save</button></form>
<table class="table"><thead><tr><th>Name</th><th>Category</th><th>Actions</th></tr></thead><tbody>
<?php foreach($services as $svc): ?><tr><td><?= htmlspecialchars($svc['name']) ?></td><td><?= htmlspecialchars($svc['category']) ?></td>
<td><form method="POST" class="d-inline"><input type="hidden" name="edit_id" value="<?= (int)$svc['id'] ?>"><button name="edit_service" class="btn btn-primary btn-sm">Edit</button></form>
<form method="POST" class="d-inline"><input type="hidden" name="delete_id" value="<?= (int)$svc['id'] ?>"><button name="delete_service" class="btn btn-danger btn-sm">Delete</button></form></td></tr><?php endforeach; ?></tbody></table>
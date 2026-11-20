<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
include_once 'includes/categories-handler.php';
?>
<h2>Manage Categories</h2><form method="POST" class="row g-2 mb-3">
<div class="col-md-8"><input class="form-control" name="category_name" placeholder="Category Name" required></div>
<div class="col-md-4"><button class="btn btn-primary" name="add_category">Add Category</button></div></form>
<?php if(!empty($message)): ?><p><?= htmlspecialchars($message) ?></p><?php endif; ?>
<table class="table"><thead><tr><th>ID</th><th>Name</th><th></th></tr></thead><tbody>
<?php foreach($categories as $cat): ?><tr><td><?= (int)$cat['id'] ?></td><td><?= htmlspecialchars($cat['name']) ?></td>
<td><form method="POST"><input type="hidden" name="delete_id" value="<?= (int)$cat['id'] ?>"><button class="btn btn-danger btn-sm" name="delete_category">Delete</button></form></td></tr><?php endforeach; ?></tbody></table>
<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
include_once 'includes/content-handler.php';
?>
<h2>Manage Content</h2>
<form method="POST" enctype="multipart/form-data">
<div class="mb-2"><input name="title" class="form-control" placeholder="Title" required></div>
<div class="mb-2"><select class="form-select" name="category_id"><option value="0">No Category</option>
<?php foreach($categories as $cat): ?><option value="<?= (int)$cat['id'] ?>"><?= htmlspecialchars($cat['name']) ?></option><?php endforeach; ?>
</select></div>
<div class="mb-2"><input type="file" name="media" class="form-control" accept=".jpg,.jpeg,.png,.webp,.pdf"></div>
<div class="mb-2"><textarea name="body" class="form-control" rows="5" required></textarea></div>
<button class="btn btn-primary" name="add_content">Publish</button></form>
<?php if (!empty($message)): ?><p><?= htmlspecialchars($message) ?></p><?php endif; ?>
<table class="table"><thead><tr><th>Title</th><th>Category</th><th>Media</th><th>Action</th></tr></thead><tbody>
<?php foreach($contents as $item): ?><tr>
<td><?= htmlspecialchars($item['title']) ?></td><td><?= htmlspecialchars($item['category']??'') ?></td>
<td><?php if($item['media_path']): ?><a href="<?= htmlspecialchars($item['media_path']) ?>">View</a><?php endif; ?></td>
<td><form method="POST"><input name="delete_id" type="hidden" value="<?= (int)$item['id'] ?>"><button name="delete_content" class="btn btn-danger btn-sm">Delete</button></form></td>
</tr><?php endforeach; ?></tbody></table>
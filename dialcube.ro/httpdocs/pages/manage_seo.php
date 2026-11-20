<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
$message='';
if (isset($_POST['save_seo'])) {
    $page=trim($_POST['page']??''); $title=trim($_POST['title']??'');
    $keywords=trim($_POST['keywords']??''); $desc=trim($_POST['description']??'');
    if ($page!=='' && $title!=='') {
        $stmt=$conn->prepare('INSERT INTO seo (page,meta_title,meta_keywords,meta_description) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE meta_title=VALUES(meta_title),meta_keywords=VALUES(meta_keywords),meta_description=VALUES(meta_description)');
        $stmt->bind_param('ssss',$page,$title,$keywords,$desc); $stmt->execute(); $message='SEO saved';
    }
}
if (isset($_POST['delete_id'])) {
    $id=(int)$_POST['delete_id']; $stmt=$conn->prepare('DELETE FROM seo WHERE id=?');
    $stmt->bind_param('i',$id); $stmt->execute();
}
$result=$conn->query('SELECT * FROM seo ORDER BY page ASC');
?>
<h2>SEO Settings</h2>
<?php if($message): ?><div class="alert alert-info"><?= htmlspecialchars($message) ?></div><?php endif; ?>
<form method="POST" class="row g-2">
<div class="col-md-3"><input class="form-control" name="page" placeholder="Page" required></div>
<div class="col-md-3"><input class="form-control" name="title" placeholder="Meta Title" required></div>
<div class="col-md-3"><input class="form-control" name="keywords" placeholder="Keywords"></div>
<div class="col-md-3"><input class="form-control" name="description" placeholder="Description"></div>
<div class="col-12"><button class="btn btn-primary" name="save_seo">Save</button></div></form>
<table class="table mt-4"><thead><tr><th>Page</th><th>Title</th><th>Keywords</th><th>Description</th><th></th></tr></thead><tbody>
<?php while($seo=$result->fetch_assoc()): ?><tr>
<td><?= htmlspecialchars($seo['page']) ?></td><td><?= htmlspecialchars($seo['meta_title']) ?></td>
<td><?= htmlspecialchars($seo['meta_keywords']??'') ?></td><td><?= htmlspecialchars($seo['meta_description']??'') ?></td>
<td><form method="POST"><input name="delete_id" type="hidden" value="<?= (int)$seo['id'] ?>"><button class="btn btn-danger btn-sm">Delete</button></form></td>
</tr><?php endwhile; ?></tbody></table>
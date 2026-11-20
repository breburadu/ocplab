<?php
if (!isset($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
if (isset($_POST['delete_id'])) {
  $stmt=$conn->prepare('DELETE FROM contact_messages WHERE id=?');
  $id=(int)$_POST['delete_id']; $stmt->bind_param('i',$id); $stmt->execute();
}
$result=$conn->query('SELECT * FROM contact_messages ORDER BY created_at DESC');
?>
<h2>Contact Messages</h2>
<table class="table"><thead><tr><th>Name</th><th>Email</th><th>Message</th><th>Date</th><th></th></tr></thead><tbody>
<?php while($row=$result->fetch_assoc()): ?><tr>
<td><?= htmlspecialchars($row['name']) ?></td><td><?= htmlspecialchars($row['email']) ?></td>
<td><?= nl2br(htmlspecialchars($row['message'])) ?></td><td><?= htmlspecialchars($row['created_at']) ?></td>
<td><form method="POST"><input type="hidden" name="delete_id" value="<?= (int)$row['id'] ?>">
<button class="btn btn-danger btn-sm">Delete</button></form></td></tr><?php endwhile; ?></tbody></table>
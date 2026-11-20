<?php
if (empty($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
$categories=[];$services=[];$edit=null;
if (isset($_POST['save_service'])) {
    $name=trim($_POST['service_name']??''); $cid=(int)($_POST['category_id']??0);
    $description=trim($_POST['description']??'');$id=(int)($_POST['service_id']??0);
    if($name!=='' && $cid>0) {
        if($id>0) {
            $stmt=$conn->prepare('UPDATE services SET name=?,category_id=?,description=? WHERE id=?');
            $stmt->bind_param('sisi',$name,$cid,$description,$id);
        } else {
            $stmt=$conn->prepare('INSERT INTO services (name,category_id,description) VALUES (?,?,?)');
            $stmt->bind_param('sis',$name,$cid,$description);
        }
        $stmt->execute();
    }
}
if (isset($_POST['delete_service'])) {
    $id=(int)($_POST['delete_id']??0);
    if($id>0) { $stmt=$conn->prepare('DELETE FROM services WHERE id=?');$stmt->bind_param('i',$id);$stmt->execute(); }
}
if(isset($_POST['edit_service'])) {
    $id=(int)($_POST['edit_id']??0);
    $stmt=$conn->prepare('SELECT * FROM services WHERE id=?');$stmt->bind_param('i',$id);$stmt->execute();$edit=$stmt->get_result()->fetch_assoc();
}
$result=$conn->query('SELECT id,name FROM categories ORDER BY name');
while($row=$result->fetch_assoc()) $categories[]=$row;
$result=$conn->query('SELECT s.id,s.name,s.description,s.category_id,c.name AS category FROM services s LEFT JOIN categories c ON c.id=s.category_id ORDER BY s.id DESC');
while($row=$result->fetch_assoc()) $services[]=$row;
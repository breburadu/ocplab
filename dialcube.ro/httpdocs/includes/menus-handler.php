<?php
if (empty($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
$menus=[]; $message='';
if(isset($_POST['add_menu'])) {
    $label=trim($_POST['menu_label']??''); $link=trim($_POST['menu_link']??'');
    if($label!=='' && $link!=='') {
        $stmt=$conn->prepare('INSERT INTO menus (label,link) VALUES (?,?)');
        $stmt->bind_param('ss',$label,$link); $stmt->execute();$message='Menu added';
    }
}
if(isset($_POST['delete_menu'])) {
    $id=(int)($_POST['delete_id']??0);
    if($id>0) {$stmt=$conn->prepare('DELETE FROM menus WHERE id=?');$stmt->bind_param('i',$id);$stmt->execute();$message='Menu deleted';}
}
if(isset($_POST['update_menu'])) {
    $id=(int)($_POST['update_id']??0);
    $label=trim($_POST['update_label']??'');$link=trim($_POST['update_link']??'');
    if($id>0 && $label!=='' && $link!=='') {
        $stmt=$conn->prepare('UPDATE menus SET label=?,link=? WHERE id=?');
        $stmt->bind_param('ssi',$label,$link,$id);$stmt->execute();$message='Menu updated';
    }
}
$result=$conn->query('SELECT id,label,link FROM menus ORDER BY id');
while($row=$result->fetch_assoc()) $menus[]=$row;
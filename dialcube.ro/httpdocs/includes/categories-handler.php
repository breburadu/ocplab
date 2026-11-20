<?php
$categories=[]; $message='';
if (!empty($_SESSION['admin_id'])) {
    if (isset($_POST['add_category'])) {
        $name=trim($_POST['category_name']??'');
        if ($name!=='') {
            $stmt=$conn->prepare('INSERT INTO categories (name) VALUES (?)');
            $stmt->bind_param('s',$name); $stmt->execute(); $message='Category added';
        }
    }
    if (isset($_POST['delete_category'])) {
        $id=(int)($_POST['delete_id']??0);
        if($id>0) { $stmt=$conn->prepare('DELETE FROM categories WHERE id=?'); $stmt->bind_param('i',$id); $stmt->execute(); $message='Category deleted'; }
    }
    $result=$conn->query('SELECT id,name FROM categories ORDER BY id DESC');
    while($row=$result->fetch_assoc()) $categories[]=$row;
}
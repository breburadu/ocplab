<?php
if (empty($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
$categories=[];$contents=[];$message='';
$result=$conn->query('SELECT id,name FROM categories ORDER BY name');
while($row=$result->fetch_assoc()) $categories[]=$row;
if (isset($_POST['add_content'])) {
    $title=trim($_POST['title']??''); $body=trim($_POST['body']??'');
    $categoryId=(int)($_POST['category_id']??0);
    $media='';
    if(!empty($_FILES['media']['tmp_name']) && is_uploaded_file($_FILES['media']['tmp_name'])) {
        $allowed=['image/jpeg'=>'jpg','image/png'=>'png','image/webp'=>'webp','application/pdf'=>'pdf'];
        $mime=(new finfo(FILEINFO_MIME_TYPE))->file($_FILES['media']['tmp_name']);
        if(isset($allowed[$mime]) && ($_FILES['media']['size']??0)<=5242880) {
            $directory=__DIR__.'/../uploads';
            if(!is_dir($directory)) mkdir($directory,0750,true);
            $file=bin2hex(random_bytes(16)).'.'.$allowed[$mime];
            if(move_uploaded_file($_FILES['media']['tmp_name'],$directory.'/'.$file)) $media='uploads/'.$file;
        }
    }
    if($title!=='' && $body!=='') {
        $stmt=$conn->prepare('INSERT INTO content (title,category_id,body,media_path,created_at) VALUES (?,?,?,?,NOW())');
        $cat=$categoryId?:null;$stmt->bind_param('siss',$title,$cat,$body,$media);
        $stmt->execute();$message='Content added';
    }
}
if(isset($_POST['delete_content'])) {
    $id=(int)($_POST['delete_id']??0);
    if($id>0){$stmt=$conn->prepare('DELETE FROM content WHERE id=?');$stmt->bind_param('i',$id);$stmt->execute();$message='Content deleted';}
}
$result=$conn->query('SELECT c.id,c.title,c.body,c.media_path,c.created_at,cat.name AS category FROM content c LEFT JOIN categories cat ON cat.id=c.category_id ORDER BY c.id DESC');
while($row=$result->fetch_assoc()) $contents[]=$row;
<?php
$error='';
if (isset($_POST['login_admin'])) {
    $username=trim($_POST['username']??''); $password=(string)($_POST['password']??'');
    if ($username!=='' && $password!=='') {
        $stmt=$conn->prepare('SELECT id,password,access_level FROM admins WHERE username=? LIMIT 1');
        $stmt->bind_param('s',$username); $stmt->execute(); $stmt->store_result();
        if ($stmt->num_rows===1) {
            $stmt->bind_result($id,$hash,$access); $stmt->fetch();
            if (password_verify($password,$hash)) {
                session_regenerate_id(true);
                $_SESSION['admin_id']=$id; $_SESSION['access_level']=$access;
                header('Location: index.php?page=admin'); exit;
            }
        }
    }
    $error='Invalid credentials.';
}
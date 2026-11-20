<?php
if (empty($_SESSION['admin_id'])) { header('Location: index.php?page=login'); exit; }
$message=''; $socials=[];
if (isset($_POST['update_social'])) {
    $platform=trim($_POST['platform']??''); $url=trim($_POST['url']??'');
    if($platform!=='' && filter_var($url,FILTER_VALIDATE_URL) && in_array(parse_url($url,PHP_URL_SCHEME),['http','https'],true)) {
        $stmt=$conn->prepare('REPLACE INTO social_links (platform,url) VALUES (?,?)');
        $stmt->bind_param('ss',$platform,$url);$stmt->execute();$message='Link updated';
    } else $message='Invalid link';
}
$result=$conn->query('SELECT platform,url FROM social_links ORDER BY platform');
while($row=$result->fetch_assoc()) $socials[]=$row;
<?php
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;
require_once __DIR__.'/../config.php';
$success=''; $error='';
if (($_SERVER['REQUEST_METHOD']??'GET')==='POST' && isset($_POST['submit_contact'])) {
    $name=trim((string)($_POST['name']??''));
    $email=trim((string)($_POST['email']??''));
    $message=trim((string)($_POST['message']??''));
    $now=time();
    $started=(int)($_POST['form_time']??0);
    if (($_POST['website']??'')!=='' || $started<=0 || $started>$now || ($now-$started)<5) {
        $error='Please retry the form.';
    } elseif (strlen($name)>255 || $name==='' || strlen($message)>10000 || $message==='' || !filter_var($email,FILTER_VALIDATE_EMAIL)) {
        $error='Please provide a valid name, email and message.';
    } elseif (($now-($_SESSION['last_contact_time']??0))<60) {
        $error='Please wait before submitting another message.';
    } else {
        $_SESSION['last_contact_time']=$now;
        try {
            $stmt=$conn->prepare('INSERT INTO contact_messages (name,email,message,created_at) VALUES (?,?,?,NOW())');
            $stmt->bind_param('sss',$name,$email,$message);$stmt->execute();
            $success='Thank you! Your message has been received.';
            $autoload=__DIR__.'/../vendor/autoload.php';
            if (!is_file($autoload)) throw new RuntimeException('Composer dependencies not installed');
            require_once $autoload;
            $settings=require __DIR__.'/../config/email.php';
            $mail=new PHPMailer(true);
            $mail->isSMTP();
            $mail->Host=$settings['host'];
            $mail->SMTPAuth=true;
            $mail->Username=$settings['username'];
            $mail->Password=$settings['password'];
            $mail->SMTPSecure=$settings['encryption'];
            $mail->Port=$settings['port'];
            // Verify remote TLS certificates; never allow self-signed certificates silently.
            $mail->setFrom($settings['from_email'],$settings['from_name']);
            $mail->addAddress(getenv('CONTACT_TO') ?: 'dial@dialcube.ro','Dialcube Admin');
            $mail->addReplyTo($email,$name);
            $mail->isHTML(true);
            $mail->Subject='New Dialcube contact message';
            $mail->Body='<strong>Name:</strong> '.htmlspecialchars($name,ENT_QUOTES).' <strong>Email:</strong> '.
                htmlspecialchars($email,ENT_QUOTES).'<p>'.nl2br(htmlspecialchars($message,ENT_QUOTES)).'</p>';
            $mail->AltBody=$name.' <'.$email.'>'."\n\n".$message;
            $mail->send();
        } catch (Throwable $e) {
            error_log('Dialcube contact delivery failure: '.$e->getMessage());
            if ($success!=='') $success='Your message was saved, but the email notification could not be delivered.';
            else $error='Could not save your message. Please retry.';
        }
    }
}
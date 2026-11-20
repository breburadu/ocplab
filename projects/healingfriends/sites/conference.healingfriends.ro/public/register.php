<?php

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\SMTP;
use PHPMailer\PHPMailer\Exception;

require 'vendor/autoload.php';
require 'vendor/phpmailer/phpmailer/src/Exception.php';
require 'vendor/phpmailer/phpmailer/src/PHPMailer.php';
require 'vendor/phpmailer/phpmailer/src/SMTP.php';
require 'vendor/phpmailer/phpmailer/src/OAuth.php';

// Set the maximum allowed form submissions per IP
$maxAttempts = 3;
$ip = $_SERVER['REMOTE_ADDR']; // Get the IP address of the user
$ipLogFile = 'ip_log.txt'; // File to track IPs, emails, and their submission count

// Read the file if it exists
$ipLogs = file_exists($ipLogFile) ? file($ipLogFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];
$ipAttempts = [];

// Parse the IP logs
foreach ($ipLogs as $log) {
    list($loggedIp, $loggedEmail, $count) = explode(',', $log);
    $ipAttempts[$loggedIp] = ['email' => $loggedEmail, 'count' => $count];
}

// Check if the IP has exceeded the maximum number of attempts
if (isset($ipAttempts[$ip]) && $ipAttempts[$ip]['count'] >= $maxAttempts) {
    // Show error and stop execution
    echo "<script>alert('Ați depășit numărul maxim de încercări. Vă rugăm să încercați din nou mai târziu.'); window.location.href = 'index.php';</script>";
    exit;
}

// Read the event date from event_date.txt
$eventDateFile = 'event_date.txt';
if (file_exists($eventDateFile)) {
    $eventDateStr = file_get_contents($eventDateFile);
    $eventDate = DateTime::createFromFormat('dmY', trim($eventDateStr));
    $currentDate = new DateTime();

    // Check if the event date has passed
    if ($currentDate > $eventDate) {
        echo "<script>alert('Înscrierile la acest eveniment s-au încheiat.Va multumim pentru interes si va asteptam la alte evenimente!'); window.location.href = 'index.php';</script>";
        exit;
    }
} else {
    // If the event date file does not exist, show an error
    echo "<script>alert('Data evenimentului nu a fost găsită. Încercați mai târziu.'); window.location.href = 'index.php';</script>";
    exit;
}

// Continue with form processing if the IP hasn't exceeded the limit
if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $name = htmlspecialchars($_POST['name']);
    $email = htmlspecialchars($_POST['email']);
    $telephone = htmlspecialchars($_POST['telephone']);

    // Check for duplicates across any of the three fields
    $file = 'registrants.txt';
    $isDuplicate = false;

    if (file_exists($file)) {
        $registrants = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        foreach ($registrants as $registrant) {
            list($regName, $regEmail, $regPhone) = explode(", ", $registrant);
            $regName = str_replace('Nume: ', '', $regName);
            $regEmail = str_replace('Email: ', '', $regEmail);
            $regPhone = str_replace('Telefon: ', '', $regPhone);

            if ($regName === $name || $regEmail === $email || $regPhone === $telephone) {
                $isDuplicate = true;
                break;
            }
        }
    }

    if (!$isDuplicate) {
        // Save registrant to file
        $content = "Nume: $name, Email: $email, Telefon: $telephone\n";
        file_put_contents('registrants.txt', $content, FILE_APPEND);

        // Load email content from email.txt and personalize it
        $emailTextContent = file_get_contents('email.txt');
        $emailTextContent = str_replace('{{name}}', $name, $emailTextContent); // Replace placeholder with the user's name

        // Format the email content as HTML
        $emailContent = "
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }
                .container {
                    width: 100%;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }
                .header {
                    background-color: #4CAF50;
                    padding: 10px;
                    color: white;
                    text-align: center;
                    border-radius: 5px 5px 0 0;
                }
                .content {
                    padding: 20px;
                    font-size: 16px;
                    line-height: 1.6;
                    color: #333;
                }
                .footer {
                    text-align: center;
                    padding: 10px;
                    font-size: 12px;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class='container'>
                <div class='header'>
                    <h1>Confirmare Inregistrare</h1>
                </div>
                <div class='content'>
                    $emailTextContent
                </div>
                <div class='footer'>
                    <p>Va multumim pentru Inregistrare !</p>
                </div>
            </div>
        </body>
        </html>";

        // Initialize PHPMailer and configure SMTP
        $mail = new PHPMailer(true);

        try {
            // Server settings
            $mail->isSMTP();
            $mail->SMTPDebug = 0;

            // Disable SSL check
            $mail->SMTPOptions = array(
                'ssl' => array(
                    'verify_peer' => false,
                    'verify_peer_name' => false,
                    'allow_self_signed' => true
                )
            );
            
            // SMTP configuration
            $mail->Host = getenv('HF_SMTP_HOST') ?: 'healingfriends.ro';
            $mail->SMTPAuth = true;
            $mail->Username = getenv('HF_SMTP_USERNAME') ?: 'office@healingfriends.ro'; 
            $mail->Password = getenv('HF_SMTP_PASSWORD') ?: ''; 
            $mail->SMTPSecure = "tls";
            $mail->Port = 587;

            // Emulate a common email client
            $mail->XMailer = 'Microsoft Outlook 16.0'; 
            $mail->addCustomHeader('X-MS-TNEF-Correlator', ''); 
            $mail->addCustomHeader('X-Priority', '3 (Normal)');
            $mail->addCustomHeader('X-MSMail-Priority', 'Normal');
            $mail->addCustomHeader('Importance', 'Normal');

            // Recipients
            $mail->setFrom('office@healingfriends.ro', 'Healing Friends');
            $mail->addAddress($email, $name); 
            $mail->addCC('office@healingfriends.ro'); 

            // Modify subject to include the user's name
            $mail->Subject = 'Salutare ' . $name . '! Multumim pentru interesul acordat!';

            // Content
            $mail->isHTML(true);
            $mail->Body = $emailContent;
            $mail->AltBody = strip_tags($emailContent); 

            $mail->send();
            
            // Success popup and redirect to index.php
            echo "<script>alert('Pre Inregistrarea a fost efectuata cu succes! Va rugam urmariti adresa de email folosita in procesul de inregistrare pentru informatii aditionale! Va multumim!'); window.location.href = 'index.php';</script>";
            
            // Increment IP count or add a new entry
            if (!isset($ipAttempts[$ip])) {
                $ipAttempts[$ip] = ['email' => $email, 'count' => 2];
            } else {
                $ipAttempts[$ip]['count']++;
            }

            // Write updated IP attempts to the file
            $ipLogEntries = [];
            foreach ($ipAttempts as $loggedIp => $data) {
                $ipLogEntries[] = "$loggedIp,{$data['email']},{$data['count']}";
            }
            file_put_contents($ipLogFile, implode("\n", $ipLogEntries));

            exit;
        } catch (Exception $e) {
            echo "Eroare la trimiterea emailului: {$mail->ErrorInfo}";
        }
    } else {
        // Handle duplicates - generate a popup error and redirect
        echo "<script>alert('Sunteti deja inregistrat! Va rugam urmariti adresa de mail folosita in procesul de inregistrare! Va multumim!'); window.location.href = 'index.php';</script>";
        exit;
    }
} else {
    // Redirect to index.php if the form is not submitted
    header("Location: index.php");
    exit;
}

?>
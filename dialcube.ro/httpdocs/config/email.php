<?php
return [
    'host' => getenv('SMTP_HOST') ?: 'mailgw.dialcube.ro',
    'username' => getenv('SMTP_USER') ?: 'contact@mailgw.dialcube.ro',
    'password' => getenv('SMTP_PASSWORD') ?: '',
    'port' => (int)(getenv('SMTP_PORT') ?: 587),
    'encryption' => 'tls',
    'from_email' => getenv('SMTP_FROM') ?: 'contact@mailgw.dialcube.ro',
    'from_name' => 'Dialcube Website',
];

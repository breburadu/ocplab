<?php
return [
    'host'        => 'mailgw.dialcube.ro',
    'username'    => 'contact@mailgw.dialcube.ro',
    'password'    => (getenv('SMTP_PASSWORD') ?: ''),
    'port'        => 587,
    'encryption'  => 'tls',
    'from_email'  => 'contact@mailgw.dialcube.ro',
    'from_name'   => 'Dialcube Website'
];

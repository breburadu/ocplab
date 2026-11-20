<?php
session_start();
// Supply production values via web server environment or local untracked bootstrap.
define('DB_HOST', getenv('DB_HOST') ?: 'localhost');
define('DB_USER', getenv('DB_USER') ?: 'dialcube');
define('DB_PASS', getenv('DB_PASS') ?: '');
define('DB_NAME', getenv('DB_NAME') ?: 'dialcubesite');
define('BASE_URL', getenv('BASE_URL') ?: 'https://dialcube.ro/');
date_default_timezone_set('Europe/Bucharest');
$conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($conn->connect_error) { error_log('Database connection failed'); http_response_code(503); exit('Service temporarily unavailable'); }
$conn->set_charset('utf8mb4');

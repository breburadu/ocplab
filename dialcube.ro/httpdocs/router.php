<?php
function route() {
    $page = $_GET['page'] ?? 'home';

    // Whitelist of allowed pages (explicit control)
    $allowed = [
        'home',
        'about',
        'services',
        'contact',
        'login',
        'logout',
        'admin',
        'manage_categories',
        'manage_menus',
        'manage_content',
        'manage_seo',
        'manage_social',
        'manage_services',
		'manage_messages'
    ];

    if (!in_array($page, $allowed)) {
        $page = '404';
    }

    $file = __DIR__ . "/pages/{$page}.php";

    if (file_exists($file)) {
        include $file;
    } else {
        echo "<div class='text-center text-danger'><h2>Page not found</h2></div>";
    }
}

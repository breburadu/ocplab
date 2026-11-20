# Source inventory

The supplied event application includes `index.php`, `register.php`, `composer.json`, `composer.lock`, event texts and legal notices. These belong under `sites/conference.healingfriends.ro/public/` because they rely on relative file paths.

The `registrants.txt` attachment contains personal data and must not be versioned. The SMTP password in the original `register.php` must be rotated. The payment details in `email.txt` should be configured securely before deployment.

Binary assets `event.jpg` and `fav.webp` are available as attachments, but have not yet been pushed. The application references `gdprro` and `event_price.txt`, which are missing from the upload. Main website and Roundcube customization sources were not attached.

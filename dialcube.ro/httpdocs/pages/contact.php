<?php include_once 'includes/contact-handler.php'; ?>
<div class="row"><div class="col-md-6 offset-md-3"><h2>Contact Us</h2>
<?php if (!empty($success)): ?><div class="alert alert-success"><?= htmlspecialchars($success) ?></div><?php endif; ?>
<?php if (!empty($error)): ?><div class="alert alert-danger"><?= htmlspecialchars($error) ?></div><?php endif; ?>
<form method="POST" class="contact-form">
<div class="mb-3"><label>Name</label><input name="name" class="form-control" maxlength="255" required></div>
<div class="mb-3"><label>Email</label><input type="email" name="email" maxlength="254" class="form-control" required></div>
<input type="text" name="website" style="display:none" tabindex="-1" autocomplete="off">
<input type="hidden" name="form_time" value="<?= time() ?>">
<div class="mb-3"><label>Message</label><textarea name="message" class="form-control" rows="5" required></textarea></div>
<button type="submit" name="submit_contact" class="btn btn-primary">Send</button></form></div></div>
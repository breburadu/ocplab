<?php
$query = $conn->query("SELECT c.id AS cat_id, c.name AS category, s.id AS service_id, s.name AS service_name, s.description FROM categories c LEFT JOIN services s ON c.id=s.category_id ORDER BY c.name,s.name");
$categories=[];
while ($row=$query->fetch_assoc()) {
    $cid=(int)$row['cat_id'];
    if (!isset($categories[$cid])) $categories[$cid]=['name'=>$row['category'],'services'=>[]];
    if ($row['service_id']) $categories[$cid]['services'][]=$row;
}
?>
<div class="container mt-5"><h2 class="text-center mb-4">Our Services</h2>
<div class="accordion" id="categories">
<?php foreach($categories as $id=>$cat): ?>
<div class="accordion-item"><h3 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#cat<?= $id ?>"><?= htmlspecialchars($cat['name']) ?></button></h3>
<div id="cat<?= $id ?>" class="accordion-collapse collapse" data-bs-parent="#categories"><div class="accordion-body">
<?php if (!$cat['services']): ?><p>No services yet in this category.</p><?php endif; ?>
<?php foreach($cat['services'] as $service): ?><p><strong><?= htmlspecialchars($service['service_name']) ?></strong><br><?= nl2br(htmlspecialchars($service['description']??'')) ?></p><?php endforeach; ?>
</div></div></div>
<?php endforeach; ?></div></div>
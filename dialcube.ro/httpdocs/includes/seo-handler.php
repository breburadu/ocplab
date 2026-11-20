<?php
// Legacy helper retained for compatibility. The SEO management page performs its own saves.
$seoEntries=[];
$result=$conn->query('SELECT * FROM seo ORDER BY page ASC');
while($row=$result->fetch_assoc()) $seoEntries[]=$row;
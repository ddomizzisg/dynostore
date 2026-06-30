<?php

require_once "models/Catalog.php";

$api = new Catalog();

// print_r($_GET);
if (isset($_GET['type'])) {
	$type = $_GET['type'];
	switch ($type) {
		case 1:
			$api->manageCatalog();
			break;
		case 2:
			$api->insertFileInCatalog($_GET['catalog'], $_GET['keyobject']);
			break;
		case 3:
			$api->listFilesInCatalog($_GET['catalog']);
			break;
		case 4:
			$api->getSubscribedCatalogs();
			break;
		case 5:
			$api->getSubCatalogs();
			break;
		default:
			$api->notFound();
			break;
	}
}else{
	$api->notFound();	
}

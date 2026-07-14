<?php
require_once "Rest.php";
require_once "db/DbHandler.php";
require_once "Curl.php";


class Catalog extends REST
{

    public function manageCatalog()
    {
        $resMet = $this->getRequestMethod();
        if ($resMet == "PUT") {
            $this->createCatalog();
        } else if ($resMet == "GET") {
            $this->getCatalog();
        } else if ($resMet == "DELETE") {
            $this->deleteCatalog();
        } 
        else {
            $this->methodNotAllowed();
        }
    }

    public function deleteCatalog(){
        if(isset($_GET['catalog'])){
            $catalog = $_GET['catalog'];
            $db = new DbHandler();
            $data = $db->deleteCatalog($catalog);
            if($data){
                $msg['message'] = "Catalog deleted";
                $this->response($this->json($msg), 200);
            }else{
                $msg['message'] = "Catalog not found";
                $this->response($this->json($msg), 404);
            }
        }else{
            $msg['message'] = "Catalog not found";
            $this->response($this->json($msg), 404);
        }
    }

    public function getCatalog(){
        if(isset($_GET['catalog'])){
            $catalog = $_GET['catalog'];
            $db = new DbHandler();
            $data = $db->getCatalog($catalog);
            if($data){
                $msg['message'] = "Catalog found";
                $msg['data'] = $data;
                $this->response($this->json($msg), 200);
            }else{
                $msg['message'] = "Catalog not found";
                $this->response($this->json($msg), 404);
            }
        }else{
            $msg['message'] = "Catalog not found";
            $this->response($this->json($msg), 404);
        }
    
    }

    public function getSubscribedCatalogs() {
        if ($this->getRequestMethod() != "GET") {
            $this->methodNotAllowed();
            return;
        }
        if(isset($_GET['tokenuser'])){
            $db = new DbHandler();
            $catalogs = $db->getCatalogsByUser_Sub($_GET['tokenuser']);
            
            // Filter only root catalogs (father == '/')
            $rootCatalogs = [];
            if ($catalogs) {
                foreach($catalogs as $cat) {
                    if ($cat['father'] == '/') {
                        $rootCatalogs[] = $cat;
                    }
                }
            }

            $msg['message'] = "Success";
            $msg['data'] = $rootCatalogs;
            $this->response($this->json($msg), 200);
        } else {
            $msg['message'] = "tokenuser not provided";
            $this->response($this->json($msg), 400);
        }
    }

    public function getSubCatalogs() {
        if ($this->getRequestMethod() != "GET") {
            $this->methodNotAllowed();
            return;
        }
        if(isset($_GET['father'])){
            $db = new DbHandler();
            $catalogs = $db->getSubCatalogs($_GET['father']);
            
            $msg['message'] = "Success";
            $msg['data'] = $catalogs ? $catalogs : [];
            $this->response($this->json($msg), 200);
        } else {
            $msg['message'] = "father not provided";
            $this->response($this->json($msg), 400);
        }
    }

    public function createCatalog()
    {
        if (
            isset ($_GET['catalog']) && isset ($this->_request['dispersemode']) &&
            isset ($this->_request['encryption']) && isset ($this->_request['fathers_token'])
        ) {
            $tokenuser = $_GET['tokenuser'];
            $catalogname = $_GET['catalog'];
            $catalogname = str_replace(" ", "_", $catalogname);
            $fatherstoken = $this->_request['fathers_token'];
            $dispersemode = $this->_request['dispersemode'];
            $encryption = $this->_request['encryption'];
            $processed = $this->_request['processed'];
            $group = $this->_request['group'];
            $db = new DbHandler();

            #check if catalog exists otherwise create it, this throw a 302 when catalog exists
            $this->validateCatalogExist($catalogname, $tokenuser);

            $keycatalog = $this->generateToken();
            $tokenC = $this->generateSHA256Token();
            //print_r($response);
            if ($fatherstoken == '/') {
                $data = $db->newCatalog(
                    $keycatalog,
                    $tokenC,
                    $catalogname,
                    $tokenuser,
                    $dispersemode,
                    $encryption,
                    $fatherstoken,
                    $group,
                    $processed
                );

                if ($data) {
                    $status = 'Owner';
                    $db->insertUsers_Catalogs($tokenuser, $tokenC, $status);
                    //$msg['message'] = "Created: ".$catalogname;                
                    $msg['message'] = "Created";
                    $msg['data'] = array("tokencatalog" => $tokenC);
                    $this->response($this->json($msg), 201);
                } else {
                    $msg = array("message" => "Cannot insert catalog into user table.");
                    $this->response($this->json($msg), 404);
                }
            } else {
                $father = $this->tokenFatherCExist($fatherstoken);
                
                if (!$father) {
                    # Father does not exist, create a new catalog with the given father name
                    $father_name = $fatherstoken; // Assuming the father token is actually the name
                    $father_keycatalog = $this->generateToken();
                    $father_tokenC = $this->generateSHA256Token();
                    $father_data = $db->newCatalog(
                        $father_keycatalog,
                        $father_tokenC,
                        $father_name,
                        $tokenuser,
                        $dispersemode,
                        $encryption,
                        '/',
                        $group,
                        $processed
                    );
                    if ($father_data) {
                        $status = 'Owner';
                        $db->insertUsers_Catalogs($tokenuser, $father_tokenC, $status);
                        $fatherstoken = $father_tokenC; // Update fatherstoken to the newly created father's token
                    } else {
                        $msg = array("message" => "Cannot create father catalog.");
                        $this->response($this->json($msg), 404);
                    }  
                }else {
                    $fatherstoken = $father['tokencatalog']; // Use the existing father's token
                }
                
                $data = $db->newCatalog(
                    $keycatalog,
                    $tokenC,
                    $catalogname,
                    $tokenuser,
                    $dispersemode,
                    $encryption,
                    $fatherstoken,
                    $group,
                    $processed
                );
                if ($data) {
                    $status = "Owner";
                    $db->insertUsers_Catalogs($tokenuser, $tokenC, $status);
                    $msg['message'] = "Created: " . $catalogname;
                    $msg['data'] = array("tokencatalog" => $tokenC);
                    $this->response($this->json($msg), 201);
                } else {
                    $msg = array("message" => "Something went wrong.2");
                    $this->response($this->json($msg), 404);
                }
            }
        } else {
            $msg['message'] = "Invalid data.";
            $this->response($this->json($msg), 400);
        }
    }

    private function generateToken()
    {
        //return hash('sha256',join('',array(time(),rand())));
        return sha1(join('', array(time(), rand())));
    }

    private function generateSHA256Token()
    {
        return hash('sha256', join('', array(time(), rand())), false);
    }

    public function insertFileInCatalog($token_catalog, $keyfile)
    {
        if ($this->getRequestMethod() != "POST") {
            $msg = array("message" => "Method not available.");
            $this->response($this->json($msg), 404);
        }

        if (isset ($keyfile) && isset ($token_catalog)) {
            $db = new DbHandler();

            if($db->catalogFileExist($token_catalog, $keyfile)){
                $msg['message'] = "Object already in catalog.";
                $this->response($this->json($msg), 302);
            }else{
                $status = 3;
                $owner = true;
                $data = $db->createCatalogFile($token_catalog, $keyfile, $status);
                if ($data) {
                    $msg['message'] = "Object inserted in catalog successfully.";
                    $this->response($this->json($msg), 201);
                } else {
                    $msg['message'] = "Error adding object to catalog.";
                    $this->response($this->json($msg), 400);
                }
            }

            
        } else {
            $msg = array("message" => "Object key or catalog missing.");
            $this->response($this->json($msg), 400);
        }
    }

    public function methodNotAllowed()
    {
        $msg = array("Error" => "Method Not Allowed.");
        $this->response($this->json($msg), 405);
    }


    public function notFound()
    {
        $msg = array("Error" => "Not Found.");
        $this->response($this->json($msg), 404);
    }

    public function tokenFatherCExist($father)
    {
        $db = new DbHandler();
        $data = $db->tokenFatherCExist($father);
        if (!$data) {
            #$msg['message'] = "Invalid data 2.";
            #$this->response($this->json($msg), 400);
            # Father does not exist, create a new catalog with the given father name
            return false;
        } else {
            return $data;
        }
    }

    public function validateCatalogExist($name, $tokenuser)
    {
        $db = new DbHandler();
        $data = $db->validateCatalogExist($name, $tokenuser);
        if ($data) {
            $msg['message'] = "Cant use this catalog name.";
            $msg['data'] = $data;
            $this->response($this->json($msg), 302);
        }
    }

    public function listFilesInCatalog($token_catalog){
        ini_set('memory_limit', '1024M');
        if ($this->getRequestMethod() != "GET") {
            $msg = array("message" => "Method not available.");
            $this->response($this->json($msg), 404);
        }

        if (isset ($token_catalog)) {
            $db = new DbHandler();
            $files = $db->getFilesByCatalog($token_catalog);
            #print_r($files);
            $msg['message'] = "Data found";
            $msg['data'] = $files;
            $this->response($this->json($msg), 201);
        } else {
            $msg = array("message" => "Object key or catalog missing.");
            $this->response($this->json($msg), 400);
        }
    }
}
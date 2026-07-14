<?php

require_once dirname(__FILE__) . '/Connection.php';
require_once dirname(__FILE__) . '../../log/Log.php';

class DbHandler {
	/**
	* @var db
	* @var log
	*/
	private $db;
	private $log;

	/**
	* DbHandler constructor.
	*/
	public function __construct() {
		$db = new Connection();
		$this->db = $db->getConnection();
		$this->log = new Log;
	}

	public function getLastInsertId() {
        try{
            return $this->db->lastInsertId();
        }catch(PDOException $e) {
            $this->log->lwrite($e->getMessage());
            return false;
        }
    }

	public function isOwnerCatalog($id) {
		try {
			$sql = 'SELECT name FROM catalogs WHERE created_by= ?;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id ,PDO::PARAM_STR);			
			if ($stmt->execute()) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/*------------- notifications ------------------*/
	public function getNotifications($keyuser) {
		try {
			//$sql = "SELECT * FROM subscribe WHERE keyuser=? AND status='1';";
			$sql = "SELECT id,keyuser,s.keycatalog,status,namecatalog FROM subscribe AS s JOIN catalogs AS c ON s.keycatalog=c.keycatalog WHERE created_by=? AND status='1';";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);			
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function allowNotification($key) {
		try {
			$sql = "UPDATE subscribe SET status=2 WHERE id=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_INT);			
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function denyNotification($key) {
		try {
			$sql = "DELETE FROM subscribe WHERE id=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_INT);			
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/*------------- notifications groups ------------------*/
	public function getNotificationsGroups($keyuser) {
		try {
			$sql = "SELECT id,keyuser,g.keygroup,status,namegroup FROM users_groups AS ug JOIN groups AS g ON ug.keygroup=g.keygroup WHERE ug.keygroup IN (SELECT keygroup FROM users_groups WHERE keyuser=?) AND status='1' AND isowner=false;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);			
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function allowNotificationGroup($key) {
		try {
			$sql = "UPDATE users_groups SET status=2 WHERE id=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_INT);			
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function denyNotificationGroup($key) {
		try {
			$sql = "DELETE FROM users_groups WHERE id=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_INT);			
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/*------------- subcribe ------------------*/
	public function subcribe($keyuser, $keycatalog) {
		try {
			$sql = "INSERT INTO user_catalog(keyuser, keycatalog) VALUES(:id,:kc);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $keyuser, PDO::PARAM_STR);			
			$stmt->bindParam(":kc", $keycatalog, PDO::PARAM_STR);			
			if ($stmt->execute()) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	//--------------------------------------------------------------------------
    //--------------------------- VISUALIZATION -------------------------------
	//--------------------------------------------------------------------------
	
	//------------------------------------------------
    //------------------ viewFiles --------------------
	//------------------------------------------------
	public function catalogTokenExist($catalog) {
		try {
			$sql = "SELECT * FROM catalogs WHERE tokencatalog=:kc;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $catalog, PDO::PARAM_STR);
			$stmt->execute();
// 			print_r($stmt);
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
// 			echo "hola";
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getFilesByCatalog($key) {
		

		try {
			$sql = "SELECT token_file FROM catalogs_files WHERE tokencatalog=?;";
			
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			//print_r($stmt->fetchAll(PDO::FETCH_ASSOC));
			//print_r($stmt->rowCount());
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = array();
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getSubCatalogs($key) {
		try {
			$sql = "SELECT * FROM catalogs  WHERE father=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			//print_r($stmt->fetchAll(PDO::FETCH_ASSOC));
			//print_r($stmt->rowCount());
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
				
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	//------------------------------------------------
    //------------------ viewCatalogs --------------------
	//------------------------------------------------
	
	public function getCatalogInfo($keycat) {
		try {
			//$sql = "SELECT * FROM groups AS s JOIN catalogs AS c ON s.keygroup=c.father WHERE keygroup=?;";
			$sql = "SELECT * FROM catalogs WHERE tokencatalog=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keycat, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByGroup($keygroup) {
		try {
			//$sql = "SELECT * FROM groups AS s JOIN catalogs AS c ON s.keygroup=c.father WHERE keygroup=?;";
			$sql = "SELECT * FROM groups_catalogs AS gc JOIN catalogs AS c ON gc.keycatalog=c.keycatalog WHERE keygroup=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keygroup, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getPublicGroups(){
		try {
			$sql = "select * from groups where isprivate = 'F'";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByUser($key) {
		try {
			$sql = "SELECT * FROM users_catalogs AS uc JOIN catalogs AS c ON uc.tokencatalog=c.tokencatalog WHERE uc.token_user=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByUser_Sub($key) {
		try {
			$sql = "SELECT * FROM users_catalogs AS uc JOIN catalogs AS c ON uc.tokencatalog=c.tokencatalog WHERE 
						uc.token_user=? AND (uc.status='Owner' OR uc.status='Published');";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getPublicCatalogs(){
		try {
			$sql = "select tokencatalog from catalogs as c inner join groups as g on c.group = g.tokengroup where g.isprivate = 'F'";
			$stmt = $this->db->prepare($sql);
			$stmt->execute();
			
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByUser_Pub($key) {
		try {
			$sql = "SELECT * FROM users_catalogs AS uc JOIN catalogs AS c ON uc.tokencatalog=c.tokencatalog WHERE uc.token_user=? AND uc.status='Published';";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByUser_Own($key) {
		try {
			$sql = "SELECT * FROM users_catalogs AS uc JOIN catalogs AS c ON uc.tokencatalog=c.tokencatalog WHERE uc.token_user=? AND uc.status='Owner';";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsByPuzzle($key, $puzzle, $father){
		try {
			//print_r($father);
			$sql = "SELECT * FROM users_catalogs AS uc JOIN catalogs AS c ON uc.tokencatalog=c.tokencatalog WHERE c.father=? AND uc.token_user=?;";
			$stmt = $this->db->prepare($sql);
			#echo $sql;
			//echo $father;
			$stmt->bindParam(1, $father, PDO::PARAM_STR);
			$stmt->bindParam(2, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			echo $e->getMessage();
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	public function getCatalogsByUser2($key) {
		try {
			$sql = "SELECT * FROM catalogs WHERE token_user=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}



	

	//------------------------------------------------
    //------------------ viewUsers --------------------
	//------------------------------------------------

	public function getUsersByGroup_Sub($key) {
		try {
			//$sql = "SELECT token_user AS tokenuser,status FROM users_groups WHERE tokengroup=?;";
			$sql = "SELECT token_user AS tokenuser,status FROM users_groups WHERE tokengroup=? AND (status='Owner' OR status='Sub');";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getUsersByGroup_Pub($key) {
		try {
			//$sql = "SELECT token_user AS tokenuser,status FROM users_groups WHERE tokengroup=?;";
			$sql = "SELECT token_user AS tokenuser,status FROM users_groups WHERE tokengroup=? AND status='Pub';";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function groupKeyExist($keyg) {
		try {
			$sql = "SELECT * FROM groups WHERE keygroup=:kc;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $keyg, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getUsersByCatalog($catalogId) {
		try {
			$sql = 'SELECT * FROM users_catalogs WHERE keycatalog = ?';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $catalogId, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	//------------------------------------------------
    //------------------ viewGroups --------------------
	//------------------------------------------------

	public function getGroupsByCatalog($key) {
		try {
			$sql = "SELECT * FROM groups_catalogs AS gc JOIN groups AS g ON gc.tokengroup=g.tokengroup WHERE gc.tokencatalog=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function catalogKeyExist($keyc) {
		try {
			$sql = "SELECT * FROM catalogs WHERE keycatalog=:kc;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $keyc, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	public function getGroupsByUser_Sub($key) {
		try {
			$sql = "SELECT * FROM users_groups AS ug JOIN groups AS g ON ug.tokengroup=g.tokengroup WHERE ug.token_user=?
			 			AND (status='Owner' OR status='Sub' OR status='Published');";
			//$sql = "SELECT * FROM users_groups AS ug JOIN groups AS g ON ug.tokengroup=g.tokengroup WHERE ug.token_user=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getGroupsByUser_Pub($key) {
		try {
			$sql = "SELECT * FROM users_groups AS ug JOIN groups AS g ON ug.tokengroup=g.tokengroup WHERE ug.token_user=? AND status='Pub';";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getGroupsByUser2($key) {
		try {
			$sql = "SELECT * FROM groups WHERE token_user=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	

	


	//------------------------------------------------
    //------------------ viewPublications --------------------
	//------------------------------------------------

	public function getPublicationsByCatalog($keycatalog) {
		try {
			$sql = "SELECT * FROM publications AS p JOIN catalogs AS c ON p.keycatalog=c.keycatalog WHERE keycatalog=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keycatalog, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function selectChildrenPub($val) {
		try {
			$sql = 'SELECT keyuser FROM catalogs WHERE father=:prt;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":prt",$val,PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getPublicationsByUser($key) {
		try {
			$sql = "SELECT * FROM publications AS p JOIN catalogs AS c ON p.keycatalog=c.keycatalog WHERE p.keyuser=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}





	//------------------------------------------------
    //------------------ publications --------------------
	//------------------------------------------------
	
	public function newPublication($keyc,$keyuser) {
		try {
			$sql = "INSERT INTO publications(keyuser, keycatalog) VALUES(:ku,:kc);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(":kc", $keyc, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function deletePublication($keyc,$keyuser) {
		try {
			$sql = "DELETE FROM publications WHERE keycatalog=:kc AND keyuser=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $keyc, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function modifyPublication($key,$name) {
		try {
				$sql = 'UPDATE publications SET status=:na WHERE id=:id;';
				$stmt = $this->db->prepare($sql);
				$stmt->bindParam(":na", $name, PDO::PARAM_STR);
				$stmt->bindParam(":id", $key, PDO::PARAM_STR);
				$stmt->execute();
				if ($stmt->rowCount()>0) {
					// group created successfully
					$res = true;
				}else{
					$res = false;
				}
				$stmt = null;
				return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function publicationExist($key,$keyuser) {
		try {
			$sql = "SELECT * FROM publications WHERE tokencatalog=:kc AND tokenuser=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $key, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

    //------------------ pub groups --------------------	
	public function groupTokenExist($group) {
		try {
			$sql = "SELECT * FROM groups WHERE tokengroup=:kc;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $group, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function newPubGroupToUser($user,$group,$status) {
		try {
			$sql = "INSERT INTO users_groups(token_user, tokengroup, status) VALUES(:user,:group,:st);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":user", $user, PDO::PARAM_STR);
			$stmt->bindParam(":group", $group, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function pubGroupToUserExist($group,$user) {
		try {
			$sql = "SELECT * FROM users_groups WHERE token_user=:usr AND tokengroup=:gp;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":usr", $user, PDO::PARAM_STR);
			$stmt->bindParam(":gp", $group, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

    //------------------ pub catalogs --------------------		
	public function newPubCatalogToUser($user,$catalog,$status) {
		try {
			$sql = "INSERT INTO users_catalogs(token_user, tokencatalog, status) VALUES(:user,:catalog,:st);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":user", $user, PDO::PARAM_STR);
			$stmt->bindParam(":catalog", $catalog, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function newPubCatalogToGroup($catalog,$group,$status) {
		try {
			$sql = "INSERT INTO groups_catalogs(tokencatalog, tokengroup, status) VALUES(:catalog,:group,:st);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":catalog", $catalog, PDO::PARAM_STR);
			$stmt->bindParam(":group", $group, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	//------------------------------------------------
    //------------------ subscriptions --------------------
	//------------------------------------------------

    //------------------ sub group --------------------	
	public function newSubGroupToUser($user,$group,$status) {
		try {
			$sql = "UPDATE users_groups SET status=:st WHERE token_user=:user AND tokengroup=:group;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":user", $user, PDO::PARAM_STR);
			$stmt->bindParam(":group", $group, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function newsubscription($keyc,$keyuser) {
		try {
			$sql = "INSERT INTO subscriptions(keyuser, keycatalog) VALUES(:ku,:kc);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(":kc", $keyc, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function deletesubscription($keyc,$keyuser) {
		try {
			$sql = "DELETE FROM subscriptions WHERE keycatalog=:kc AND keyuser=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $keyc, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function modifysubscription($key,$name) {
		try {
				$sql = 'UPDATE subscriptions SET status=:na WHERE id=:id;';
				$stmt = $this->db->prepare($sql);
				$stmt->bindParam(":na", $name, PDO::PARAM_STR);
				$stmt->bindParam(":id", $key, PDO::PARAM_STR);
				$stmt->execute();
				if ($stmt->rowCount()>0) {
					// group created successfully
					$res = true;
				}else{
					$res = false;
				}
				$stmt = null;
				return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function subscriptionExist($key,$keyuser) {
		try {
			$sql = "SELECT * FROM subscriptions WHERE keycatalog=:kc AND keyuser=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $key, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}




	//------------------------------------------------
    //------------------ catalogs --------------------
    //------------------------------------------------

	public function newCatalog($keyc,$token,$namec,$keyuser,$dispersemode,$encryption,$father,$group,$processed) {
		try {
			$processed = isset($processed) ? $processed : "false" ;
			$sql = "INSERT INTO catalogs(keycatalog,tokencatalog, namecatalog, token_user, dispersemode, encryption, father, \"group\", processed) VALUES(:id,:tk,:na,:cb,:dm,:enc,:ft, :gp, :pr);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $keyc, PDO::PARAM_STR);
			$stmt->bindParam(":tk", $token, PDO::PARAM_STR);
			$stmt->bindParam(":na", $namec, PDO::PARAM_STR);
			$stmt->bindParam(":cb", $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(":dm", $dispersemode, PDO::PARAM_STR);
			$stmt->bindParam(":enc", $encryption, PDO::PARAM_BOOL);
			$stmt->bindParam(":ft", $father, PDO::PARAM_STR);
			$stmt->bindParam(":gp", $group, PDO::PARAM_STR);
			$stmt->bindParam(":pr", $processed, PDO::PARAM_BOOL);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function deleteCatalog($keyc) {
		try {
			$sql = "DELETE FROM catalogs WHERE tokencatalog=:id;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $keyc, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	

	public function modifyCatalog($cat,$namec,$disperse,$encryp) {
		try {
				$sql = 'UPDATE catalogs SET namecatalog=:na, dispersemode=:dm, encryption=:enc WHERE tokencatalog=:id;';
				$stmt = $this->db->prepare($sql);
				$stmt->bindParam(":na", $namec, PDO::PARAM_STR);
				$stmt->bindParam(":dm", $disperse, PDO::PARAM_STR);
				$stmt->bindParam(":enc", $encryp, PDO::PARAM_BOOL);
				$stmt->bindParam(":id", $cat, PDO::PARAM_STR);
				$stmt->execute();
				if ($stmt->rowCount() > 0) {
					// catalog created successfully
					$res = true;
				}else{
					$res = false;
				}
				$stmt = null;
				return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function validateCatalogExist($name,$tokenuser) {
		try {
			$sql = "SELECT * FROM catalogs AS c INNER JOIN users_catalogs as uc ON uc.tokencatalog = c.tokencatalog WHERE namecatalog=:na AND uc.token_user=:tu;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":na", $name, PDO::PARAM_STR);
			$stmt->bindParam(":tu", $tokenuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function tokenFatherCExist($key) {
		try {
			$sql = "SELECT tokencatalog FROM catalogs WHERE tokencatalog=:kc or namecatalog=:kc2;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $key, PDO::PARAM_STR);
			$stmt->bindParam(":kc2", $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function tokenCatalogExist($catalog,$user) {
		try {
			$sql = "SELECT * FROM catalogs WHERE tokencatalog=:kc AND token_user=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $catalog, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $user, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function insertUsers_Catalogs($user,$catalog,$status) {
		try {
			$sql = "INSERT INTO users_catalogs(token_user,tokencatalog,status) VALUES(:ku,:kg,:st);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $user, PDO::PARAM_STR);
			$stmt->bindParam(":kg", $catalog, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}









	/**
	* @return array|mixed
	*/
	public function getAllCatalogs() {
		try {
			$sql = 'SELECT * FROM catalogs;';
			$stmt = $this->db->prepare($sql);
			if ($stmt->execute()) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	

	/**
	* @return array|mixed
	*/
	public function getCatalog($id) {
		try {
			$sql = 'SELECT * FROM catalogs WHERE tokencatalog = ? OR namecatalog = ?;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id ,PDO::PARAM_STR);
			$stmt->bindParam(2, $id ,PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function insertCatalogToGroup($keygroup, $keycatalog) {
		try {
			$sql = "INSERT INTO groups_catalogs(keygroup,keycatalog) VALUES(?,?);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keygroup, PDO::PARAM_STR);
			$stmt->bindParam(2, $keycatalog, PDO::PARAM_STR);
			$result = $stmt->execute();
			if ($result) {
					$response = true;
			}else{
					$response = false;
			}
			$stmt = null;
			return $response;			
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function validateSubscribe($keyuser,$keycatalog) {
		try {
			$sql = "SELECT status FROM subscribe WHERE keyuser=? AND keycatalog=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(2, $keycatalog, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
					$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
					$res = 0;
			}
			$stmt = null;
			return $res;			
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function validateSubscribeGroup($keyuser,$keygroup) {
		try {
			$sql = "SELECT status FROM users_groups WHERE keyuser=? AND keygroup=?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(2, $keygroup, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
					$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
					$res = 0;
			}
			$stmt = null;
			return $res;			
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function subscribe($keyuser,$keycatalog,$status) {
		try {
			$sql = "INSERT INTO subscribe VALUES(DEFAULT,?,?,?);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(2, $keycatalog, PDO::PARAM_STR);
			$stmt->bindParam(3, $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$response = true;
			}else{
					$response = false;
			}
			$stmt = null;
			return $response;			
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function subscribeGroup($keyuser,$keygroup,$status) {
		try {
			$sql = "INSERT INTO users_groups(keyuser,keygroup,status) VALUES(?,?,?);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(2, $keygroup, PDO::PARAM_STR);
			$stmt->bindParam(3, $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$response = true;
			}else{
					$response = false;
			}
			$stmt = null;
			return $response;			
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}
	
	

	/**
	* Creating new catalog
	* @param String $catalog      Catalog
	* @param String $userId       User id
	* @return [type]              [description]
	*/
	public function createCatalog($catalog) {
		//$this->db->beginTransaction();
		//$this->db->rollBack();
		//$this->db->commit();
		try {
				
				$created = $this->newCatalog($catalog);
				if($created){
					$status = 3;
					$subs=$this->subscribe($catalog['keyuser'],$catalog['keycatalog'],$status);
					if ($subs) {
						
						$res['res'] = "OK";
						$res['data'] = $catalog['keycatalog'];
					}
				}else{
					$res = "COULDNT_CREATE"; 
				}
			
			return $res;		
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}
	
	public function getAvaliableCatalogs($id) {
		try {
			$sql = "SELECT * FROM subscribe AS s JOIN catalogs AS c ON s.keycatalog=c.keycatalog WHERE keyuser<>?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id ,PDO::PARAM_STR);	
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}




	/**
	* Function to assign a catalog to user
	* @param String $userId     User id
	* @param String $catalogId  Catalog id
	* @return [type]            [description]
	*/
	public function createUserCatalog($userId, $catalogId) {
		try {
			$sql = 'INSERT INTO user_catalogs(user_id, catalog_id) VALUES(?, ?)';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $userId, PDO::PARAM_INT);
			$stmt->bindParam(2, $catalogId, PDO::PARAM_INT);
			if ($stmt->execute()) {
				$user = true;
			} else {
				$user = false;
			}
			$stmt = null;
			return $user;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/**
	* Fetching all user catalogs
	* @param String $userId  User id
	* @return Array          Catalogs
	*/
	public function getAllUserCatalogs($token) {
		try {
			$sql = 'SELECT * FROM catalogs WHERE token_user = ?';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $token, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getCatalogsWithAccess($keyuser) {
		try {
			$sql = "SELECT * FROM subscribe AS s JOIN catalogs AS c ON s.keycatalog=c.keycatalog WHERE keyuser=? AND (status='2' OR status='3');";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$users = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$users = false;
			}
			$stmt = null;
			return $users;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	


	/**
	* Fetching single catalog
	* @param  String $catalogId Catalog id
	* @param  String $userId    User id
	* @return Array             Catalog info
	*/
	public function getCatalogUser($catalogId, $userId) {
		try {
			$sql = 'SELECT c.id, c.name, c.status, c.created_at FROM catalogs c, user_catalogs uc WHERE c.id = ? AND uc.user_id = ? AND uc.catalog_id = c.id';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $catalogId, PDO::PARAM_STR);
			$stmt->bindParam(2, $userId, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$catalog = $stmt->fetch(PDO::FETCH_ASSOC);
			} else {
				$catalog = false;
			}
			$stmt = null;
			return $catalog;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/**
	* @param $id
	* @return bool
	*/
	public function deleteSubs($id) {
		try {
			$sql = "DELETE FROM subscribe WHERE keycatalog = ?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id, PDO::PARAM_STR);
			$stmt->execute();
			$sql = "DELETE FROM catalogs WHERE keycatalog = ?;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				return true;
			} else {
				return false;
			}
			$stmt = null;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		} 
	}

	/**
	* Function to assign a file to catalog
	* @param String $catalogId   Catalog id
	* @param String $fileId      File id
	* @return [type]             [description]
	*/
	public function createCatalogFile($catalogId, $fileId, $status){
		try {
			$sql = 'INSERT INTO catalogs_files(tokencatalog, token_file,status) VALUES(?,?,?) returning *;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $catalogId, PDO::PARAM_STR);
			$stmt->bindParam(2, $fileId, PDO::PARAM_STR);
			$stmt->bindParam(3, $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	/**
	 * Check if catalog contains file
	 */
	public function catalogFileExist($catalogId, $fileId) {
		try {
			$sql = 'SELECT * FROM catalogs_files WHERE tokencatalog = ? AND token_file = ?;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $catalogId, PDO::PARAM_STR);
			$stmt->bindParam(2, $fileId, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}
	
	
	/**
	* Fetching all user files
	* @param String $userId     User id
	* @param String $catalogId  Catalog id
	* @return Array             Files
	*/
	public function getCatalogFiles($tokenc) {
		try {
			$sql = 'SELECT token_file AS keyfile FROM catalogs_files WHERE tokencatalog = ?';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $tokenc, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}




	//------------------------------------------------
    //------------------ groups --------------------
	//------------------------------------------------
	
	public function newGroup($key,$token,$name,$user,$father,$isprivate) {
		try {
			$sql = "INSERT INTO groups(keygroup,tokengroup, namegroup, token_user, father, isprivate) VALUES(:id,:tk,:na,:cb,:ft,:ip);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $key, PDO::PARAM_STR);
			$stmt->bindParam(":tk", $token, PDO::PARAM_STR);
			$stmt->bindParam(":na", $name, PDO::PARAM_STR);
			$stmt->bindParam(":cb", $user, PDO::PARAM_STR);
			$stmt->bindParam(":ft", $father, PDO::PARAM_STR);
			$stmt->bindParam(":ip", $isprivate);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function insertUsers_Groups($user,$group,$status) {
		try {
			$sql = "INSERT INTO users_groups(token_user,tokengroup,status) VALUES(:ku,:kg,:st);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $user, PDO::PARAM_STR);
			$stmt->bindParam(":kg", $group, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function deleteGroup($key) {
		try {
			$sql = "DELETE FROM groups WHERE tokengroup=:id;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function deleteGroupByKey($key) {
		try {
			$sql = "DELETE FROM groups WHERE keygroup=:id;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
					$res = true;
			}else{
					$res = false;
			}
			$stmt = null;
			return $res;					
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function modifyGroup($key,$name) {
		try {
				$sql = 'UPDATE groups SET namegroup=:na WHERE tokengroup=:id;';
				$stmt = $this->db->prepare($sql);
				$stmt->bindParam(":na", $name, PDO::PARAM_STR);
				$stmt->bindParam(":id", $key, PDO::PARAM_STR);
				$stmt->execute();
				if ($stmt->rowCount() > 0) {
					// group created successfully
					$res = true;
				}else{
					$res = false;
				}
				$stmt = null;
				return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function validateGroupExistByToken($token) {
		try {
			$sql = "SELECT * FROM groups WHERE tokencatalog=:na;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":na", $token, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function validateGroupExist($name,$tokenuser) {
		try {
			$sql = "SELECT * FROM groups WHERE namegroup=:na AND token_user=:tu;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":na", $name, PDO::PARAM_STR);
			$stmt->bindParam(":tu", $tokenuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function tokenfatherGExist($key) {
		try {
			$sql = "SELECT * FROM groups WHERE tokengroup=:kg;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kg", $key, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function tokenGroupExist($group,$user) {
		try {
			$sql = "SELECT * FROM groups WHERE tokengroup=:kc AND token_user=:ku;";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":kc", $group, PDO::PARAM_STR);
			$stmt->bindParam(":ku", $user, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				$res = $stmt->fetch(PDO::FETCH_ASSOC);
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	//--------------------------- view down -------------------------------
	public function selectChildrenG($val) {
		try {
			$sql = 'SELECT keygroup FROM groups WHERE father=:va;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":va",$val,PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() > 0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

















	// groups and subgroups with access
	public function getGroupsWithAccess($keyuser) {
		try {
			//$sql = 'SELECT * FROM groups WHERE keygroup IN (SELECT keygroup FROM groups WHERE created_by=:ku) OR keygroup IN (SELECT keygroup FROM groups WHERE parent_key IN (SELECT keygroup FROM groups WHERE created_by=:ku);';
			$sql = "SELECT * FROM groups AS g JOIN users_groups AS ug ON g.keygroup=ug.keygroup WHERE ug.keyuser=:ku AND ug.status='2';";
			//SELECT * FROM groups AS g JOIN users_groups AS ug ON g.keygroup=ug.keygroup WHERE g.keygroup IN (SELECT keygroup FROM users_groups WHERE keyuser='5a2b564940fcda436379a6d18a614a8429a51fdb') AND ug.status='2';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getAvaliableGroups($id) {
		try {
			$sql = "SELECT * FROM groups AS g JOIN users_groups AS ug ON g.keygroup=ug.keygroup WHERE g.keygroup NOT IN (SELECT keygroup FROM users_groups WHERE keyuser=:ku) AND g.ispublic=true;";
			// SELECT * FROM groups AS g JOIN users_groups AS ug ON g.keygroup=ug.keygroup WHERE g.keygroup NOT IN (SELECT keygroup FROM users_groups WHERE keyuser='5a2b564940fcda436379a6d18a614a8429a51jg4') AND g.ispublic=true;
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(1, $id ,PDO::PARAM_STR);	
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$catalogs = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$catalogs = false;
			}
			$stmt = null;
			return $catalogs;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}


	
	
	public function relationUsersGroups($keyuser,$keygroup,$status,$admin,$owner) {
		try {
			$sql = "INSERT INTO users_groups(keyuser, keygroup, status, isadmin, isowner) VALUES(:ku,:kg,:st,:ad,:ow);";
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":ku", $keyuser, PDO::PARAM_STR);
			$stmt->bindParam(":kg", $keygroup, PDO::PARAM_STR);
			$stmt->bindParam(":st", $status, PDO::PARAM_STR);
			$stmt->bindParam(":ad", $admin, PDO::PARAM_BOOL);
			$stmt->bindParam(":ow", $owner, PDO::PARAM_BOOL);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function insertIntoGroups($key,$name,$father,$public) {
		try {
			$sql = 'INSERT INTO groups(keygroup, namegroup, father, ispublic) VALUES(:id,:na,:fa,:pu);';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":id", $key, PDO::PARAM_STR);
			$stmt->bindParam(":na", $name, PDO::PARAM_STR);
			$stmt->bindParam(":fa", $father, PDO::PARAM_STR);
			$stmt->bindParam(":pu", $public, PDO::PARAM_BOOL);
			$stmt->execute();
			if ($stmt->rowCount()==1) {
				$res = true;
			}else{
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	

	public function validateGroup($name, $userId) {
		try {
			//$sql = 'SELECT * FROM groups WHERE namegroup=:na OR (namegroup=:na AND created_by=:cb);';
			$sql = 'SELECT * FROM groups WHERE namegroup=:na;';
			$stmt = $this->db->prepare($sql);
			$stmt->bindParam(":na", $name, PDO::PARAM_STR);
			//$stmt->bindParam(":cb", $userId, PDO::PARAM_STR);
			$stmt->execute();
			if ($stmt->rowCount() == 1) {
				$res = false;
			}else{
				$res = true;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}



	

	/**
	* Generating random Unique MD5 String for user Api key
	* @return String    User api key
	*/
	private function generateToken() {
		//return hash('sha256',join('',array(time(),rand())));
		return sha1(join('',array(time(),rand())));
	}

	/**
	* @desc Close connection
	*/
	public function __destruct() {
		$this->db = null;
	}






	//------------------------------------------------
    //------------------ dev only --------------------
    //------------------------------------------------
	
	public function deleteAllC() {
		try {
			$sql = 'DELETE FROM catalogs_files;';
			$stmt = $this->db->prepare($sql);
			$sb=$stmt->execute();
			$sql = 'DELETE FROM groups_files;';
			$stmt = $this->db->prepare($sql);
			$cf=$stmt->execute();
			$sql = 'DELETE FROM users_files;';
			$stmt = $this->db->prepare($sql);
			$cat=$stmt->execute();
			//$sql = 'DELETE FROM users_groups;';
			//$stmt = $this->db->prepare($sql);
			//$ug=$stmt->execute();
			//$sql = 'DELETE FROM groups;';
			//$stmt = $this->db->prepare($sql);
			//$gp=$stmt->execute();
			if ($sb && $cat && $cf && $ug && $gp) {
				return true;
			} else {
				return false;
			}
			$stmt = null;
		} catch (PDOException $e) {
			$this->log->lwrite($e->getMessage());
			return false;
		} 
	}

	public function getAllGroups() {
		try {
			$sql = 'SELECT * FROM groups;';
			$stmt = $this->db->prepare($sql);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$groups = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$groups = false;
			}
			$stmt = null;
			return $groups;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}

	public function getTest() {
		try {
			//$sql = 'SELECT * FROM catalogs_files;';
			$sql = 'SELECT * FROM publications;';
			$stmt = $this->db->prepare($sql);
			$stmt->execute();
			if ($stmt->rowCount()>0) {
				$res = $stmt->fetchAll(PDO::FETCH_ASSOC);
			} else {
				$res = false;
			}
			$stmt = null;
			return $res;
		} catch (PDOException $e) {
			$stmt = null;
			$this->log->lwrite($e->getMessage());
			return false;
		}
	}



}

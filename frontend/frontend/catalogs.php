<?php
include_once("includes/config.php");

include_once(SESIONES);
include_once(CLASES . "/Curl.php");

//INICIA LA SESIÓN
Sessions::startSession("muyalpainal");


if (empty($_SESSION['tokenuser'])) {
  header("Location: login.php");
}

$curl = new Curl();
$url = $_ENV['APIGATEWAY_HOST'] . '/pub_sub/v1/view/groups/user/' . $_SESSION['tokenuser'] . '/subscribed?access_token=' . $_SESSION['access_token'];
$curl = new Curl();
$response = $curl->get($url);
$groups  = $response["data"]["data"];

?>

<!DOCTYPE html>
<html lang="en">
<!-- header -->
<?php
$title = "Dashboard";
include_once(VISTAS .  "/components/head.php");
?>

<body>

  <!-- Preloader 
<div class="preloader">
    <div class="preloader-icon"></div>
</div>
./ Preloader -->

  <!-- Layout wrapper -->
  <div class="layout-wrapper">
    <?php
    include_once(VISTAS .  "/components/header_bar.php");

    ?>

    <!-- Content wrapper -->
    <div class="content-wrapper">
      <?php include_once(VISTAS .  "/components/menu.php"); ?>

      <!-- Content body -->
      <div class="content-body">
        <!-- Content -->
        <div class="content">
          <div class="page-header d-flex justify-content-between">
            <h2>Explorador de catálogos</h2>
            <a href="#" class="files-toggler">
              <i class="ti-menu"></i>
            </a>
          </div>

          <div class="row">
            <div class="col-xl-4 files-sidebar">
              <div class="card shadow-sm mb-4" style="border-radius: 10px;">
                <div class="card-body">
                  <h6 class="card-title mb-4">Mis catálogos</h6>
                  <div id="files"></div>
                </div>
              </div>
            </div>
            <div class="col-xl-8">
              <div class="card shadow-sm" style="border-radius: 10px;">
                <div class="card-body">
                  <div class="content-title mt-0 d-flex justify-content-between align-items-center">
                    <h4 class="mb-0">Contenidos</h4>
                    <div class="dropdown">
                      <a href="#" class="btn btn-primary dropdown-toggle shadow-sm" data-toggle="dropdown" style="border-radius: 8px;">
                        Crear Nuevo
                      </a>
                      <div class="dropdown-menu dropdown-menu-right">
                        <a class="dropdown-item" data-toggle="modal" data-target="#createGroup" style="cursor: pointer">
                          <i class="ti-user mr-2"></i>Grupo
                        </a>
                        <a class="dropdown-item" data-toggle="modal" data-target="#createCatalog" style="cursor: pointer">
                          <i class="ti-folder mr-2"></i>Catálogo
                        </a>
                      </div>
                    </div>
                  </div>
                  
                  <hr class="mb-4">

                  <div class="table-responsive">
                    <table id="table-files" class="table table-hover table-striped table-bordered" style="width:100%">
                      <thead class="thead-light">
                        <tr>
                          <th>Nombre</th>
                          <th>Modificado</th>
                          <th>Creado por</th>
                          <th>Tamaño (KB)</th>
                          <th>Grupo</th>
                          <th>Acciones</th>
                        </tr>
                      </thead>
                      <tbody id="tablefilesbody">
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>


        <?php include_once("views/modals/creategroup.php"); ?>


        <div class="modal fade" id="createCatalog" tabindex="-1" role="dialog" aria-hidden="true">
          <div class="modal-dialog modal-dialog-centered" role="document">
            <div class="modal-content">
              <form id="frmCreateCatalog">
                <div class="modal-header">
                  <h5 class="modal-title" id="exampleModalCenterTitle">Crear catálogo</h5>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <i class="ti-close"></i>
                  </button>
                </div>
                <div class="modal-body">

                  <div class="form-group">
                    <label for="txtCatalogName">Nombre del catálogo</label>
                    <input type="text" class="form-control" id="txtCatalogName" placeholder="Ingrese el nombre del catálogo" required>
                    </small>
                  </div>
                  <!-- Select -->
                  <div class="form-group">
                    <label for="slGroup">Grupo</label>
                    <select class="form-control" id="slGroup">
                      <?php foreach ($groups as $rows) {
                        echo "<option value='" . $rows["tokengroup"] . "'>" . $rows["namegroup"] . "</option>";
                      }  ?>
                    </select>
                  </div>
                </div>

                <div class="modal-footer">
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Cerrar
                  </button>
                  <button type="submit" class="btn btn-primary">Crear</button>
                </div>
              </form>
            </div>
          </div>
        </div>



        <!-- ./ Content -->
      </div>
      <!-- ./ Content body -->

      
    </div>



  </div>

  <?php
  include_once(VISTAS .  "/components/scripts.php");
  ?>
  <!-- Datatable -->
  <script src="<?php echo PROJECT_HOME; ?>/vendors/dataTable/datatables.min.js"></script>

  <!-- Jstree -->
  <script src="<?php echo PROJECT_HOME; ?>/vendors/jstree/jstree.min.js"></script>
  <script src="<?php echo PROJECT_HOME; ?>/assets/js/catalogs.js"></script>
  <script>
    $(function() {
      $('#table-files').DataTable({
        "scrollY": "400px",
        "scrollX": "400px",
        "scrollCollapse": true,
        searching: true
      });
      getcatalogstree(true);
    });
  </script>
</body>

</html>
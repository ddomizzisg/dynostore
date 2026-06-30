<?php
include_once("includes/config.php");

include_once(SESIONES);

//INICIA LA SESIÓN
Sessions::startSession("muyalpainal");

if(empty($_SESSION['tokenuser'])){
  header("Location: login.php");
}

?>

<!DOCTYPE html>
<html lang="en">
<!-- header -->
<?php
  $title = "Dashboard";
  include_once( VISTAS .  "/components/head.php");
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
    include_once( VISTAS .  "/components/header_bar.php");
    include_once( VISTAS .  "/components/menu.php");

  ?>

    <!-- Content body -->
    <div class="content-body">
      <!-- Content -->
      <div class="content">
        <div class="page-header d-md-flex justify-content-between">
            <div>
                <h3>Bienvenido al Dashboard</h3>
                <p class="text-muted">Resumen de actividad y estado de tu cuenta.</p>
            </div>
        </div>

        <div class="row">
            <div class="col-md-4">
                <div class="card text-white bg-primary mb-3 shadow-sm" style="border-radius: 10px;">
                    <div class="card-header border-0 pb-0">Grupos</div>
                    <div class="card-body">
                        <h2 class="card-title mb-0" style="font-weight: 700;">3</h2>
                        <p class="card-text">Grupos activos en los que participas.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-info mb-3 shadow-sm" style="border-radius: 10px;">
                    <div class="card-header border-0 pb-0">Catálogos</div>
                    <div class="card-body">
                        <h2 class="card-title mb-0" style="font-weight: 700;">12</h2>
                        <p class="card-text">Total de catálogos gestionados.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-secondary mb-3 shadow-sm" style="border-radius: 10px;">
                    <div class="card-header border-0 pb-0">Almacenamiento</div>
                    <div class="card-body">
                        <h2 class="card-title mb-0" style="font-weight: 700;">45%</h2>
                        <p class="card-text">Espacio utilizado en tu cuenta.</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-8">
                <div class="card shadow-sm" style="border-radius: 10px;">
                    <div class="card-body">
                        <h5 class="card-title">Actividad Reciente</h5>
                        <ul class="list-group list-group-flush mt-3">
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                Actualización de catálogo "Ventas Q3"
                                <span class="badge badge-primary badge-pill">Hace 2 horas</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                Nuevo integrante en grupo "Desarrollo"
                                <span class="badge badge-primary badge-pill">Ayer</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                Carga de archivo completada
                                <span class="badge badge-primary badge-pill">Hace 3 días</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card shadow-sm bg-light" style="border-radius: 10px;">
                    <div class="card-body text-center">
                        <h5 class="card-title">Acciones Rápidas</h5>
                        <hr>
                        <a href="catalogs.php" class="btn btn-primary btn-block mb-3" style="border-radius: 8px;">Ir a Catálogos</a>
                        <a href="grupos.php" class="btn btn-outline-primary btn-block" style="border-radius: 8px;">Gestionar Grupos</a>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </div>

  <?php

    include_once( VISTAS .  "/components/sidebar.php");
  ?>
</div>

<?php
  include_once( VISTAS .  "/components/scripts.php");
?>
</body>
</html>
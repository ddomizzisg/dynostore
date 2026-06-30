$('#login').click(function (evt) {

    toastr.options = {
        timeOut: 3000,
        progressBar: true,
        showMethod: "slideDown",
        hideMethod: "slideUp",
        showDuration: 200,
        hideDuration: 200
    };


    // Traemos los datos de los inputs
    evt.preventDefault();
    var user = $('input[name="username"]').val();
    var clave = $('input[name="password"]').val();
    var $btn = $(this);
    
    if (!user || !clave) {
        swal('Error', 'Ingrese todos los campos', 'error');
    } else {
        // Envio de datos mediante Ajax
        console.log($("#login_form").serialize());
        $.ajax({
                method: 'POST',
                url: 'models/auth/login.php',
                data: $("#login_form").serialize(),
                // Esta funcion se ejecuta antes de enviar la información al archivo indicado en el parametro url
                beforeSend: function () {
                    $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm mr-2"></span>Iniciando...');
                    toastr.info('Validando credenciales...');
                }
            })
            .done(function (res) {
                console.log(res);
                $btn.prop('disabled', false).html('Iniciar sesión');
                if (res == 'ok') {
                    toastr.success('Inicio de sesión correcto');
                    window.location.replace("index.php");
                } else {
                    toastr.error('Error');
                }
            })
            .fail(function (res) {
                console.log(res);
                $btn.prop('disabled', false).html('Iniciar sesión');
                if (res) {
                    resJson = res.responseJSON;
                    if (resJson) {
                        switch (resJson.message) {
                            case '':
                                toastr.error('Error');
                                break;
                            default:
                                toastr.error(resJson.message);
                                break;
                        }
                    } else {
                        toastr.error('Error');
                    }
                } else {
                    toastr.error('Error');
                }
            });
    }
});


$(function () {
    toastr.options = {
        timeOut: 3000,
        progressBar: true,
        showMethod: "slideDown",
        hideMethod: "slideUp",
        showDuration: 200,
        hideDuration: 200
    };

    $("#frmCreateOrg").submit(function (evt) {
        evt.preventDefault();
        var fdata = $("#frmCreateOrg").serialize();
        console.log(fdata);

        $.ajax({
                url: 'models/auth/neworg.php',
                type: 'POST',
                data: fdata,
                dataType: "json",
                beforeSend: function () {
                    toastr.info('Creando organización');
                }
            })
            .done(function (res) {
                $('#load').html('');
                console.log("aaa");
                console.log(res);
                if (res) {
                    console.log(res);
                    //swal('Ok', 'User created, please check your email.', 'success')
                    if(res.code == 0){
                        toastr.success('Organización creada');
                        $('#createOrg').modal('hide');
                    }else{
                        toastr.error(res.data.message);
                    }
                } else {
                    toastr.error('Error');
                }
            })
            .fail(function (res) {
                console.log(res);
                toastr.error('Error');
            });
    });
});
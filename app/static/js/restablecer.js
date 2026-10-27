/* Nueva contrasena con el token del correo (Adenda 1). */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-restablecer");
    if (!formulario) return;

    var aviso = document.getElementById("aviso");
    var panelSinToken = document.getElementById("panel-sin-token");
    var panelListo = document.getElementById("panel-listo");
    var campoToken = document.getElementById("token");
    var password = document.getElementById("password");
    var confirmacion = document.getElementById("confirmacion");
    var boton = document.getElementById("btn-guardar");
    var giro = document.getElementById("giro-restablecer");

    var token = (campoToken.value || "").trim();
    if (!/^[A-Za-z0-9_-]{16,200}$/.test(token)) {
      panelSinToken.hidden = false;
      return;
    }
    formulario.hidden = false;

    formulario.addEventListener("submit", async function (evento) {
      evento.preventDefault();
      Fipca.aviso(aviso, "");
      Fipca.errorCampo(password, "");
      Fipca.errorCampo(confirmacion, "");

      var clave = password.value;
      var repetida = confirmacion.value;
      var valido = true;

      if (clave.length < 8) {
        Fipca.errorCampo(password, "Use al menos 8 caracteres.");
        valido = false;
      } else if (!/[A-Za-z]/.test(clave) || !/\d/.test(clave)) {
        Fipca.errorCampo(password, "Combine letras y numeros.");
        valido = false;
      }

      if (repetida !== clave) {
        Fipca.errorCampo(confirmacion, "Las contrasenas no coinciden.");
        valido = false;
      }

      if (!valido) {
        (clave.length < 8 ? password : confirmacion).focus();
        return;
      }

      Fipca.cargando(boton, giro, true, "Guardando...");
      try {
        await Fipca.pedir("/api/v1/auth/restablecer", {
          metodo: "POST",
          cuerpo: { token: token, password: clave },
          noRedirigir: true,
        });
        formulario.hidden = true;
        panelListo.hidden = false;
        panelListo.querySelector("a").focus();
      } catch (error) {
        if (error.estado === 400) {
          Fipca.aviso(
            aviso,
            "El enlace ya no es valido: puede haber caducado o haberse usado. Solicite uno nuevo.",
            "error"
          );
        } else {
          Fipca.aviso(aviso, error.message, "error");
        }
      } finally {
        Fipca.cargando(boton, giro, false, "Guardando...");
      }
    });
  });
})();

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
    var boton = document.getElementById("btn-guardar");
    var giro = document.getElementById("giro-restablecer");

    var token = (campoToken.value || "").trim();
    var tokenValido = token.length >= 16 && token.length <= 200;
    for (var indice = 0; tokenValido && indice < token.length; indice += 1) {
      var caracter = token.charCodeAt(indice);
      tokenValido =
        (caracter >= 48 && caracter <= 57) ||
        (caracter >= 65 && caracter <= 90) ||
        (caracter >= 97 && caracter <= 122) ||
        caracter === 45 ||
        caracter === 95;
    }
    if (!tokenValido) {
      panelSinToken.hidden = false;
      return;
    }
    formulario.hidden = false;

    formulario.addEventListener("submit", async function (evento) {
      evento.preventDefault();
      Fipca.aviso(aviso, "");
      var clave = password.value;

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

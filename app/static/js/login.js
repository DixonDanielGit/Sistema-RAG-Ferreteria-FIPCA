/* Inicio de sesion (Adenda 1).
   Envia las credenciales a la API; el servidor responde con la cookie de
   sesion HttpOnly, que este script nunca ve ni necesita ver. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-login");
    if (!formulario) return;

    var aviso = document.getElementById("aviso");
    var identificador = document.getElementById("identificador");
    var password = document.getElementById("password");
    var boton = document.getElementById("btn-entrar");
    var giro = document.getElementById("giro-login");

    var parametros = new URLSearchParams(window.location.search);
    if (parametros.has("expirada")) {
      Fipca.aviso(
        aviso,
        "Su sesion expiro por inactividad. Vuelva a ingresar.",
        "info"
      );
    } else if (parametros.has("salida")) {
      Fipca.aviso(aviso, "Sesion cerrada correctamente.", "info");
    } else if (parametros.has("restablecida")) {
      Fipca.aviso(aviso, "Contrasena actualizada. Ingrese con su clave nueva.", "exito");
    }

    formulario.addEventListener("submit", async function (evento) {
      evento.preventDefault();
      Fipca.aviso(aviso, "");

      var usuarioLimpio = identificador.value.trim();
      var clave = password.value;

      Fipca.cargando(boton, giro, true, "Entrando...");

      try {
        await Fipca.pedir("/api/v1/auth/login", {
          metodo: "POST",
          cuerpo: { identificador: usuarioLimpio, password: clave },
          noRedirigir: true,
        });
        Fipca.navegar("/dashboard", true);
      } catch (error) {
        if (error.estado === 401) {
          Fipca.aviso(aviso, "Usuario o contrasena incorrectos.", "error");
          password.value = "";
          password.focus();
        } else if (error.estado === 403) {
          Fipca.aviso(aviso, error.message, "error");
        } else if (error.estado === 429) {
          Fipca.aviso(aviso, "Demasiados intentos. Espere unos minutos.", "error");
        } else {
          Fipca.aviso(aviso, error.message, "error");
        }
      } finally {
        Fipca.cargando(boton, giro, false, "Entrando...");
      }
    });
  });
})();

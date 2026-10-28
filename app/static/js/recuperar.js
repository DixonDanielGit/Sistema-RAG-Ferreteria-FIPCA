/* Solicitud del enlace de recuperacion (Adenda 1).
   La respuesta del servidor es siempre la misma exista o no el correo: la
   interfaz no debe insinuar lo contrario. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-recuperar");
    if (!formulario) return;

    var aviso = document.getElementById("aviso");
    var correo = document.getElementById("correo");
    var boton = document.getElementById("btn-enviar");
    var giro = document.getElementById("giro-recuperar");
    var panelEnviado = document.getElementById("panel-enviado");
    var botonOtro = document.getElementById("btn-otro-correo");

    formulario.addEventListener("submit", async function (evento) {
      evento.preventDefault();
      Fipca.aviso(aviso, "");

      var valor = correo.value.trim();

      Fipca.cargando(boton, giro, true, "Enviando...");
      try {
        await Fipca.pedir("/api/v1/auth/recuperar", {
          metodo: "POST",
          cuerpo: { correo: valor },
          noRedirigir: true,
        });
        formulario.hidden = true;
        panelEnviado.hidden = false;
        panelEnviado.querySelector("button").focus();
      } catch (error) {
        if (error.estado === 429) {
          Fipca.aviso(
            aviso,
            "Se hicieron demasiadas solicitudes desde este equipo. Espere unos minutos.",
            "error"
          );
        } else {
          Fipca.aviso(aviso, error.message, "error");
        }
      } finally {
        Fipca.cargando(boton, giro, false, "Enviando...");
      }
    });

    if (botonOtro) {
      botonOtro.addEventListener("click", function () {
        panelEnviado.hidden = true;
        formulario.hidden = false;
        correo.focus();
        correo.select();
      });
    }
  });
})();

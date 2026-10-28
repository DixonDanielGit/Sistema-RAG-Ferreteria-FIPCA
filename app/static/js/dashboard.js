/* Panel principal: la consulta escrita aqui se envia al asistente.
   El panel no duplica el chat: solo transporta la pregunta hasta /chat, que
   la toma de la URL y la envia sola (ver chat.js). */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-consulta");
    if (!formulario) return;

    var campo = document.getElementById("consulta");
    var LIMITE = 2000;
    var error = document.getElementById("error-consulta");
    var interactuada = false;

    function irAlAsistente(pregunta) {
      var limpia = (pregunta || "").trim();
      if (!limpia) {
        campo.focus();
        return;
      }
      window.Fipca.navegar(
        "/chat?pregunta=" + encodeURIComponent(limpia.slice(0, LIMITE))
      );
    }

    function validarConsulta(mostrarVacio) {
      var valor = campo.value;
      var mensaje = "";
      if (!valor.trim()) {
        if (mostrarVacio) mensaje = "Escriba una consulta antes de continuar.";
      } else if (valor.length > LIMITE) {
        mensaje = "La consulta no puede superar los " + LIMITE + " caracteres.";
      } else if (valor.includes("\0")) {
        mensaje = "La consulta contiene caracteres no permitidos.";
      }

      campo.setAttribute("aria-invalid", mensaje ? "true" : "false");
      error.textContent = mensaje;
      error.hidden = !mensaje;
      return !mensaje && Boolean(valor.trim());
    }

    campo.addEventListener("input", function () {
      interactuada = true;
      validarConsulta(true);
    });
    campo.addEventListener("blur", function () {
      if (interactuada) validarConsulta(true);
    });

    formulario.addEventListener("submit", function (evento) {
      evento.preventDefault();
      if (!validarConsulta(true)) {
        campo.focus();
        return;
      }
      irAlAsistente(campo.value);
    });

    document.querySelectorAll("[data-atajo]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        irAlAsistente(boton.getAttribute("data-atajo") || "");
      });
    });
  });
})();

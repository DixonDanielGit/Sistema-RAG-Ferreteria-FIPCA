/* Panel principal: la consulta escrita aqui se envia al Buscador Comercial.
   El panel no duplica la busqueda: solo transporta el texto hasta /search,
   que lo toma de la URL y lo consulta contra PostgreSQL. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-consulta");
    if (!formulario) return;

    var campo = document.getElementById("consulta");
    var LIMITE = 200;
    var error = document.getElementById("error-consulta");
    var interactuada = false;

    function irAlBuscador(consulta) {
      var limpia = (consulta || "").trim();
      if (!limpia) {
        campo.focus();
        return;
      }
      window.Fipca.navegar(
        "/search?consulta=" + encodeURIComponent(limpia.slice(0, LIMITE))
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
      irAlBuscador(campo.value);
    });

    document.querySelectorAll("[data-atajo]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        irAlBuscador(boton.getAttribute("data-atajo") || "");
      });
    });
  });
})();

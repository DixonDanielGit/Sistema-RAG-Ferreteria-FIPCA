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

    function irAlAsistente(pregunta) {
      var limpia = (pregunta || "").trim();
      if (!limpia) {
        campo.focus();
        return;
      }
      window.location.href =
        "/chat?pregunta=" + encodeURIComponent(limpia.slice(0, LIMITE));
    }

    formulario.addEventListener("submit", function (evento) {
      evento.preventDefault();
      irAlAsistente(campo.value);
    });

    document.querySelectorAll("[data-atajo]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        irAlAsistente(boton.getAttribute("data-atajo") || "");
      });
    });
  });
})();

/* Conmutador de tema claro/oscuro.
   La preferencia vive en localStorage; al no haber eleccion guardada se
   respeta la del sistema operativo. El <head> ya aplico el tema antes de
   pintar, asi que aqui solo se sincroniza el boton y se guarda el cambio. */
(function () {
  "use strict";

  var CLAVE = "fipca-tema";

  function actual() {
    return document.documentElement.getAttribute("data-bs-theme") || "light";
  }

  function aplicar(tema) {
    document.documentElement.setAttribute("data-bs-theme", tema);
    document.documentElement.setAttribute("data-swal2-theme", tema);
    try {
      localStorage.setItem(CLAVE, tema);
    } catch (error) {
      /* navegacion privada: se aplica solo para esta pagina */
    }
    sincronizar();
  }

  function sincronizar() {
    var tema = actual();
    var oscuro = tema === "dark";
    document.documentElement.setAttribute("data-swal2-theme", tema);
    document.querySelectorAll("[data-tema-toggle]").forEach(function (boton) {
      boton.setAttribute("aria-pressed", String(oscuro));
      boton.setAttribute(
        "title",
        oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
      );
    });
    var meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute("content", oscuro ? "dark light" : "light dark");
  }

  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-tema-toggle]");
    if (!boton) return;
    aplicar(actual() === "dark" ? "light" : "dark");
  });

  /* Si el usuario nunca eligio, seguir los cambios del sistema en vivo. */
  var consulta = window.matchMedia("(prefers-color-scheme: dark)");
  consulta.addEventListener("change", function (evento) {
    try {
      if (localStorage.getItem(CLAVE)) return;
    } catch (error) {
      return;
    }
    var nuevoTema = evento.matches ? "dark" : "light";
    document.documentElement.setAttribute("data-bs-theme", nuevoTema);
    document.documentElement.setAttribute("data-swal2-theme", nuevoTema);
    sincronizar();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", sincronizar);
  } else {
    sincronizar();
  }
})();

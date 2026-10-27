/* Panel de fuentes del asistente (Adenda 1).
   Solo interfaz: los archivos se listan en el navegador y nunca se envian al
   servidor. La carga real al catalogo llega con el ETL de la Semana 3.
   Todo el texto se pinta con textContent: un nombre de archivo es dato del
   usuario y nunca se interpreta como HTML. */
(function () {
  "use strict";

  var MAX_ARCHIVOS = 20;
  var MAX_BYTES = 20 * 1024 * 1024;
  var EXTENSIONES = ["pdf", "csv", "xlsx", "xls", "docx", "txt"];

  function extension(nombre) {
    var punto = nombre.lastIndexOf(".");
    return punto === -1 ? "" : nombre.slice(punto + 1).toLowerCase();
  }

  function formatear(bytes) {
    if (bytes < 1024 * 1024) {
      return Math.max(1, Math.round(bytes / 1024)) + " KB";
    }
    return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
  }

  /* Icono de quitar, creado con DOM para no usar innerHTML con datos. */
  function iconoQuitar() {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("aria-hidden", "true");

    var trazo = document.createElementNS("http://www.w3.org/2000/svg", "path");
    trazo.setAttribute("d", "M6 6l12 12M18 6L6 18");
    svg.appendChild(trazo);
    return svg;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var panel = document.getElementById("panel-fuentes");
    if (!panel) return;

    var entrada = document.getElementById("archivos");
    var lista = document.getElementById("lista-fuentes");
    var vacio = document.getElementById("fuentes-vacio");
    var cuenta = document.getElementById("cuenta-fuentes");
    var cuentaMovil = document.getElementById("cuenta-fuentes-movil");
    var error = document.getElementById("error-fuentes");
    var zona = document.getElementById("zona-archivos");
    var boton = document.getElementById("boton-archivos");
    var abrir = document.getElementById("abrir-fuentes");
    var cerrar = document.getElementById("cerrar-fuentes");
    var velo = document.getElementById("velo-fuentes");
    var principal = document.querySelector(".chat__principal");

    var archivos = [];
    var arrastre = 0;

    function aviso(texto) {
      if (error) error.textContent = texto;
    }

    function actualizar() {
      var total = archivos.length;
      if (cuenta) {
        cuenta.textContent = total + (total === 1 ? " archivo" : " archivos");
      }
      if (cuentaMovil) cuentaMovil.textContent = String(total);
      if (vacio) vacio.hidden = total > 0;
    }

    function pintar() {
      if (!lista) return;
      lista.querySelectorAll(".fuentes__archivo").forEach(function (nodo) {
        nodo.remove();
      });

      archivos.forEach(function (archivo, indice) {
        var fila = document.createElement("li");
        fila.className = "fuentes__archivo";

        var icono = document.createElement("span");
        icono.className = "fuentes__icono";
        icono.setAttribute("aria-hidden", "true");
        icono.textContent = archivo.ext.toUpperCase();

        var datos = document.createElement("span");
        datos.className = "fuentes__datos";

        var nombre = document.createElement("span");
        nombre.className = "fuentes__nombre";
        nombre.textContent = archivo.nombre;
        nombre.title = archivo.nombre;

        var meta = document.createElement("span");
        meta.className = "fuentes__meta";
        meta.textContent = archivo.ext.toUpperCase() + " · " + formatear(archivo.tamano);

        var quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "fuentes__quitar";
        quitar.dataset.indice = String(indice);
        quitar.setAttribute("aria-label", "Quitar " + archivo.nombre);
        quitar.appendChild(iconoQuitar());

        datos.appendChild(nombre);
        datos.appendChild(meta);
        fila.appendChild(icono);
        fila.appendChild(datos);
        fila.appendChild(quitar);
        lista.appendChild(fila);
      });
    }

    function agregar(seleccion) {
      var rechazados = 0;
      var repetidos = 0;
      var sobrantes = 0;

      Array.prototype.forEach.call(seleccion, function (archivo) {
        var ext = extension(archivo.name);
        if (EXTENSIONES.indexOf(ext) === -1 || archivo.size > MAX_BYTES) {
          rechazados += 1;
          return;
        }
        var yaEsta = archivos.some(function (guardado) {
          return guardado.nombre === archivo.name && guardado.tamano === archivo.size;
        });
        if (yaEsta) {
          repetidos += 1;
          return;
        }
        if (archivos.length >= MAX_ARCHIVOS) {
          sobrantes += 1;
          return;
        }
        archivos.push({ nombre: archivo.name, tamano: archivo.size, ext: ext });
      });

      var mensajes = [];
      if (rechazados) {
        mensajes.push("Solo se aceptan PDF, Excel, CSV, Word o TXT de hasta 20 MB.");
      }
      if (sobrantes) {
        mensajes.push("La lista admite como máximo " + MAX_ARCHIVOS + " archivos.");
      }
      if (repetidos) {
        mensajes.push("Uno de los archivos ya estaba en la lista.");
      }
      aviso(mensajes.join(" "));

      pintar();
      actualizar();
    }

    function abrirSelector() {
      if (entrada) entrada.click();
    }

    if (boton) boton.addEventListener("click", abrirSelector);
    if (zona) zona.addEventListener("click", abrirSelector);

    if (entrada) {
      entrada.addEventListener("change", function () {
        agregar(entrada.files);
        entrada.value = "";
      });
    }

    /* Arrastrar y soltar sobre la zona punteada. El contador evita que el
       resaltado parpadee al pasar sobre los elementos hijos. */
    if (zona) {
      zona.addEventListener("dragenter", function (evento) {
        evento.preventDefault();
        arrastre += 1;
        zona.setAttribute("data-activa", "true");
      });
      zona.addEventListener("dragover", function (evento) {
        evento.preventDefault();
      });
      zona.addEventListener("dragleave", function () {
        arrastre = Math.max(0, arrastre - 1);
        if (arrastre === 0) zona.removeAttribute("data-activa");
      });
      zona.addEventListener("drop", function (evento) {
        evento.preventDefault();
        arrastre = 0;
        zona.removeAttribute("data-activa");
        agregar(evento.dataTransfer.files);
      });
    }

    /* Si se suelta un archivo fuera de la zona, el navegador lo abriria y se
       perderia la conversacion: se anula solo para arrastres de archivos. */
    function evitarNavegacion(evento) {
      if (
        evento.dataTransfer &&
        Array.prototype.indexOf.call(evento.dataTransfer.types, "Files") !== -1
      ) {
        evento.preventDefault();
      }
    }
    document.addEventListener("dragover", evitarNavegacion);
    document.addEventListener("drop", evitarNavegacion);

    if (lista) {
      lista.addEventListener("click", function (evento) {
        var quitar = evento.target.closest("[data-indice]");
        if (!quitar) return;
        var indice = Number(quitar.dataset.indice);
        archivos.splice(indice, 1);
        aviso("");
        pintar();
        actualizar();

        /* Al reconstruir la lista se pierde el foco: se devuelve al boton
           equivalente o, si ya no quedan archivos, al de agregar. */
        var restantes = lista.querySelectorAll(".fuentes__quitar");
        if (restantes.length) {
          restantes[Math.min(indice, restantes.length - 1)].focus();
        } else if (boton) {
          boton.focus();
        }
      });
    }

    /* Cajon del telefono: se abre sobre la conversacion y se cierra con la
       aspa, el velo o la tecla Escape. */
    var movil = window.matchMedia("(max-width: 900px)");

    function abrirPanel() {
      if (!movil.matches) return;
      panel.setAttribute("data-abierto", "true");
      if (velo) velo.hidden = false;
      if (abrir) abrir.setAttribute("aria-expanded", "true");
      /* Se lee el ancho para forzar el recalculo: sin el, el panel aun esta
         oculto y el boton de cierre no admite foco. */
      void panel.offsetWidth;
      if (cerrar) cerrar.focus();
      /* Despues de mover el foco, el resto de la vista deja de ser navegable
         mientras el cajon esta abierto. */
      if (principal) principal.inert = true;
    }

    function cerrarPanel() {
      if (panel.getAttribute("data-abierto") !== "true") return;
      panel.removeAttribute("data-abierto");
      if (velo) velo.hidden = true;
      if (principal) principal.inert = false;
      if (abrir) {
        abrir.setAttribute("aria-expanded", "false");
        abrir.focus();
      }
    }

    if (abrir) abrir.addEventListener("click", abrirPanel);
    if (cerrar) cerrar.addEventListener("click", cerrarPanel);
    if (velo) velo.addEventListener("click", cerrarPanel);

    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") cerrarPanel();
    });

    if (movil.addEventListener) {
      movil.addEventListener("change", function (evento) {
        if (evento.matches) return;
        panel.removeAttribute("data-abierto");
        if (velo) velo.hidden = true;
        if (principal) principal.inert = false;
        if (abrir) abrir.setAttribute("aria-expanded", "false");
      });
    }

    actualizar();
  });
})();

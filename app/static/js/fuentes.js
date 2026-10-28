/* Carga y estado de los catalogos que alimentan el asistente. */
(function () {
  "use strict";

  var MAX_ARCHIVOS = 20;
  var MAX_BYTES = 20 * 1024 * 1024;
  var EXTENSIONES = ["pdf", "xlsx", "docx", "txt"];
  var ETIQUETAS_ESTADO = {
    pendiente: "Pendiente",
    procesando: "Procesando",
    ok: "Cargado",
    parcial: "Cargado con errores",
    error: "No procesado",
    rechazado: "Rechazado",
  };

  function extension(nombre) {
    var punto = nombre.lastIndexOf(".");
    return punto === -1 ? "" : nombre.slice(punto + 1).toLowerCase();
  }

  function formatear(bytes) {
    if (!bytes) return "0 KB";
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
    var procesar = document.getElementById("procesar-archivos");
    var zona = document.getElementById("zona-archivos");
    var boton = document.getElementById("boton-archivos");
    var abrir = document.getElementById("abrir-fuentes");
    var cerrar = document.getElementById("cerrar-fuentes");
    var velo = document.getElementById("velo-fuentes");
    var principal = document.querySelector(".chat__principal");

    var archivos = [];
    var historial = [];
    var subiendo = false;
    var arrastre = 0;

    function aviso(texto, tipo) {
      if (!error) return;
      error.textContent = texto;
      if (texto) error.setAttribute("data-tipo", tipo || "error");
      else error.removeAttribute("data-tipo");
    }

    function actualizar() {
      var total = archivos.length + historial.length;
      if (cuenta) {
        cuenta.textContent = total + (total === 1 ? " archivo" : " archivos");
      }
      if (cuentaMovil) cuentaMovil.textContent = String(total);
      if (vacio) vacio.hidden = total > 0;
      if (procesar) procesar.disabled = archivos.length === 0 || subiendo;
      if (boton) boton.disabled = subiendo;
      if (zona) zona.disabled = subiendo;
      if (entrada) entrada.disabled = subiendo;
    }

    function pintar() {
      if (!lista) return;
      lista.querySelectorAll(".fuentes__archivo").forEach(function (nodo) {
        nodo.remove();
      });

      function agregarFila(archivo, indice, esLocal) {
        var fila = document.createElement("li");
        fila.className = "fuentes__archivo";

        var icono = document.createElement("span");
        icono.className = "fuentes__icono";
        icono.setAttribute("aria-hidden", "true");
        icono.textContent = String(archivo.ext || archivo.tipo || "").toUpperCase();

        var datos = document.createElement("span");
        datos.className = "fuentes__datos";

        var nombre = document.createElement("span");
        nombre.className = "fuentes__nombre";
        nombre.textContent = archivo.nombre;
        nombre.title = archivo.nombre;

        var meta = document.createElement("span");
        meta.className = "fuentes__meta";
        var tamano = archivo.tamano === undefined
          ? Number(archivo.tamano_bytes || 0)
          : archivo.tamano;
        var detalles = [
          String(archivo.ext || archivo.tipo || "").toUpperCase(),
          formatear(tamano),
        ];
        if (!esLocal) {
          detalles.push(ETIQUETAS_ESTADO[archivo.estado] || "Estado desconocido");
          if (archivo.filas_ok || archivo.filas_error) {
            detalles.push(
              archivo.filas_ok + " correctas, " + archivo.filas_error + " con error"
            );
          }
        }
        meta.textContent = detalles.filter(Boolean).join(" · ");

        datos.appendChild(nombre);
        datos.appendChild(meta);
        fila.appendChild(icono);
        fila.appendChild(datos);
        if (esLocal) {
          var quitar = document.createElement("button");
          quitar.type = "button";
          quitar.className = "fuentes__quitar";
          quitar.dataset.indice = String(indice);
          quitar.setAttribute("aria-label", "Quitar " + archivo.nombre);
          quitar.appendChild(iconoQuitar());
          fila.appendChild(quitar);
        } else if (archivo.detalle) {
          var detalle = document.createElement("span");
          detalle.className = "fuentes__meta";
          detalle.textContent = archivo.detalle.slice(0, 180);
          fila.title = archivo.detalle;
          datos.appendChild(detalle);
        }
        lista.appendChild(fila);
      }

      historial.forEach(function (archivo, indice) {
        agregarFila(archivo, indice, false);
      });
      archivos.forEach(function (archivo, indice) {
        agregarFila(archivo, indice, true);
      });
    }

    function agregar(seleccion) {
      var extensionesInvalidas = 0;
      var archivosVacios = 0;
      var archivosGrandes = 0;
      var repetidos = 0;
      var sobrantes = 0;

      Array.prototype.forEach.call(seleccion, function (archivo) {
        var ext = extension(archivo.name);
        if (EXTENSIONES.indexOf(ext) === -1) {
          extensionesInvalidas += 1;
          return;
        }
        if (archivo.size === 0) {
          archivosVacios += 1;
          return;
        }
        if (archivo.size > MAX_BYTES) {
          archivosGrandes += 1;
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
        archivos.push({
          nombre: archivo.name,
          tamano: archivo.size,
          ext: ext,
          archivo: archivo,
        });
      });

      var mensajes = [];
      if (extensionesInvalidas) {
        mensajes.push("Solo se aceptan archivos PDF, XLSX, DOCX o TXT.");
      }
      if (archivosVacios) {
        mensajes.push("No se pueden agregar archivos vacíos.");
      }
      if (archivosGrandes) {
        mensajes.push("Cada archivo debe pesar como máximo 20 MB.");
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

    async function cargarHistorial() {
      try {
        historial = await Fipca.pedir("/api/v1/inventario/archivos");
        pintar();
        actualizar();
      } catch (fallo) {
        aviso("No se pudo consultar el historial de catálogos.");
      }
    }

    if (procesar) {
      procesar.addEventListener("click", async function () {
        if (subiendo || archivos.length === 0) return;
        subiendo = true;
        aviso("");
        actualizar();

        var formulario = new FormData();
        archivos.forEach(function (archivo) {
          formulario.append("archivos", archivo.archivo, archivo.nombre);
        });

        try {
          var respuesta = await Fipca.pedir("/api/v1/inventario/ingesta", {
            metodo: "POST",
            cuerpo: formulario,
          });
          var cargados = respuesta.archivos_ok + respuesta.archivos_parciales;
          var conProblemas =
            respuesta.archivos_parciales +
            respuesta.archivos_error +
            respuesta.archivos_rechazados;
          archivos = [];
          var resumen = cargados + " archivo(s) cargado(s)";
          if (conProblemas) {
            var incidencias = respuesta.resultados
              .filter(function (resultado) {
                return (
                  resultado.estado === "parcial" ||
                  resultado.estado === "error" ||
                  resultado.estado === "rechazado"
                );
              })
              .map(function (resultado) {
                return resultado.nombre + ": " + (resultado.detalle || "sin detalle");
              })
              .join(". ")
              .slice(0, 700);
            resumen += "; " + conProblemas + " archivo(s) requieren revisión. " + incidencias;
          }
          aviso(resumen, conProblemas ? "error" : "exito");
          await cargarHistorial();
        } catch (fallo) {
          aviso(fallo.message || "No se pudo procesar el lote.");
        } finally {
          subiendo = false;
          pintar();
          actualizar();
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

    cargarHistorial();
    actualizar();
  });
})();

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
    return iconoTrazado("M6 6l12 12M18 6L6 18");
  }

  /* Icono de bote de basura para eliminar catalogos guardados. */
  function iconoEliminar() {
    return iconoTrazado(
      "M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"
    );
  }

  function iconoTrazado(trazo) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("aria-hidden", "true");

    var camino = document.createElementNS("http://www.w3.org/2000/svg", "path");
    camino.setAttribute("d", trazo);
    svg.appendChild(camino);
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
    var estadoSubida = document.getElementById("estado-fuentes");
    var textoEstado = document.getElementById("texto-estado-fuentes");
    var entradaBusqueda = document.getElementById("buscar-fuentes");
    var busqueda = document.getElementById("busqueda-fuentes");
    var sinCoincidencias = document.getElementById("fuentes-sin-coincidencias");
    var zona = document.getElementById("zona-archivos");
    var boton = document.getElementById("boton-archivos");
    var abrir = document.getElementById("abrir-fuentes");
    var cerrar = document.getElementById("cerrar-fuentes");
    var velo = document.getElementById("velo-fuentes");
    var principal = document.querySelector(".chat__principal");

    var archivos = [];
    var historial = [];
    var subiendo = false;
    var eliminando = false;
    var arrastre = 0;
    var consulta = "";
    var puedeEliminar = Boolean(lista && lista.dataset.puedeEliminar);

    /* La busqueda ignora mayusculas y tildes: "martillo" encuentra
       "Martínez", y "excel" encuentra archivos XLSX que lleven "Excel". */
    function normalizar(texto) {
      return String(texto || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    }

    function esVisible(archivo) {
      if (!consulta) return true;
      return normalizar(archivo.nombre).indexOf(consulta) !== -1;
    }

    function ocupacion() {
      return subiendo || eliminando;
    }

    function aviso(texto, tipo) {
      if (!error) return;
      error.textContent = texto;
      if (texto) error.setAttribute("data-tipo", tipo || "error");
      else error.removeAttribute("data-tipo");
    }

    /* Estado global de la carga: texto con spinner mientras la cola sube.
       Avanza uno a uno para no saturar el servidor (estilo Notebook). */
    function mensajeEstado(texto) {
      if (!estadoSubida) return;
      if (texto) {
        if (textoEstado) textoEstado.textContent = texto;
        estadoSubida.hidden = false;
      } else {
        estadoSubida.hidden = true;
        if (textoEstado) textoEstado.textContent = "";
      }
    }

    function actualizar() {
      var total = archivos.length + historial.length;
      if (cuenta) {
        cuenta.textContent = total + (total === 1 ? " archivo" : " archivos");
      }
      if (cuentaMovil) cuentaMovil.textContent = String(total);
      if (vacio) vacio.hidden = total > 0;
      /* El buscador solo tiene sentido con archivos que filtrar; sin ellos
         se oculta y se limpia para no dejar un filtro dormido. */
      if (busqueda) {
        if (total === 0) {
          busqueda.hidden = true;
          consulta = "";
          if (entradaBusqueda && entradaBusqueda.value) entradaBusqueda.value = "";
        } else {
          busqueda.hidden = false;
        }
      }
      if (boton) boton.disabled = ocupacion();
      if (zona) zona.disabled = ocupacion();
      if (entrada) entrada.disabled = ocupacion();
      if (lista) {
        lista.querySelectorAll(".fuentes__eliminar").forEach(function (nodo) {
          nodo.disabled = ocupacion();
        });
      }
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
        if (esLocal) {
          /* Estados de la cola de subida automatica. */
          var etiqueta = { cola: "En cola", subiendo: "Subiendo…" }[archivo.estado];
          detalles.push(etiqueta || ETIQUETAS_ESTADO[archivo.estado]);
        } else {
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
          /* La cola no se puede mutar mientras sube: los indices y el limite
             por lote dejarian de ser consistentes. */
          if (!subiendo) {
            var quitar = document.createElement("button");
            quitar.type = "button";
            quitar.className = "fuentes__quitar";
            quitar.dataset.indice = String(indice);
            quitar.setAttribute("aria-label", "Quitar " + archivo.nombre);
            quitar.appendChild(iconoQuitar());
            fila.appendChild(quitar);
          } else if (archivo.estado === "subiendo") {
            var giro = document.createElement("span");
            giro.className = "fuentes__cargando";
            giro.setAttribute("aria-hidden", "true");
            fila.appendChild(giro);
          }
        } else {
          if (archivo.detalle) {
            var detalle = document.createElement("span");
            detalle.className = "fuentes__meta";
            detalle.textContent = archivo.detalle.slice(0, 180);
            fila.title = archivo.detalle;
            datos.appendChild(detalle);
          }
          if (puedeEliminar && archivo.id_archivo) {
            var eliminar = document.createElement("button");
            eliminar.type = "button";
            eliminar.className = "fuentes__eliminar";
            eliminar.dataset.idArchivo = String(archivo.id_archivo);
            eliminar.disabled = ocupacion();
            eliminar.setAttribute(
              "aria-label",
              "Eliminar el catálogo " + archivo.nombre +
                " y sus productos asociados"
            );
            eliminar.appendChild(iconoEliminar());
            fila.appendChild(eliminar);
          }
        }
        lista.appendChild(fila);
      }

      var visibles = 0;
      historial.forEach(function (archivo, indice) {
        if (!esVisible(archivo)) return;
        visibles += 1;
        agregarFila(archivo, indice, false);
      });
      archivos.forEach(function (archivo, indice) {
        if (!esVisible(archivo)) return;
        visibles += 1;
        agregarFila(archivo, indice, true);
      });
      /* Con filtro activo y lista llena pero sin resultados, se anuncia
         para no dejar un panel en blanco sin explicacion. */
      if (sinCoincidencias) {
        sinCoincidencias.hidden = !(consulta && visibles === 0);
      }
    }

    function agregar(seleccion) {
      /* Notebook-style: hasta que la cola no termina no se aceptan mas
         archivos, para no colapsar la API con cargas en paralelo. */
      if (subiendo) {
        aviso(
          "Espere a que terminen de subirse los archivos en cola " +
            "antes de agregar más."
        );
        return;
      }
      var extensionesInvalidas = 0;
      var archivosVacios = 0;
      var archivosGrandes = 0;
      var repetidos = 0;
      var sobrantes = 0;
      var agregados = 0;

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
          estado: "cola",
          archivo: archivo,
        });
        agregados += 1;
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
      /* Subida automatica: nada de botones, se procesa apenas se agrega
         un archivo valido (aunque el lote tenga que revisar otros). */
      if (agregados) subirCola();
    }

    async function subirCola() {
      if (subiendo || !archivos.length) return;
      subiendo = true;
      aviso("");
      pintar();
      actualizar();

      var cargados = 0;
      var incidencias = [];
      try {
        for (var i = 0; i < archivos.length; i++) {
          var item = archivos[i];
          item.estado = "subiendo";
          pintar();
          mensajeEstado(
            "Subiendo y procesando archivo " + (i + 1) + " de " +
              archivos.length + "…"
          );

          var formulario = new FormData();
          formulario.append("archivos", item.archivo, item.nombre);
          try {
            var respuesta = await Fipca.pedir("/api/v1/inventario/ingesta", {
              metodo: "POST",
              cuerpo: formulario,
            });
            var resultado = respuesta.resultados[0];
            item.estado = resultado.estado;
            item.detalle = resultado.detalle || "";
            cargados += respuesta.archivos_ok + respuesta.archivos_parciales;
            if (resultado.estado !== "ok") {
              incidencias.push(
                resultado.nombre + ": " + (resultado.detalle || "sin detalle")
              );
            }
          } catch (fallo) {
            item.estado = "error";
            item.detalle = fallo.message || "No se pudo subir el archivo.";
            incidencias.push(item.nombre + ": " + item.detalle);
          }
        }

        if (incidencias.length) {
          aviso(
            cargados + " archivo(s) cargado(s); los demás requieren revisión. " +
              incidencias.join(". ").slice(0, 700),
            "error"
          );
        } else {
          aviso(
            cargados + " archivo(s) cargado(s) y procesado(s) correctamente.",
            "exito"
          );
        }
      } finally {
        subiendo = false;
        mensajeEstado("");
        archivos = [];
        await cargarHistorial();
        pintar();
        actualizar();
      }
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

    /* Buscador del panel: filtra sin recargar ni volver a pedir el
       historial, igual que lo hace la lista de chat del asistente. */
    if (entradaBusqueda) {
      entradaBusqueda.addEventListener("input", function () {
        consulta = normalizar(entradaBusqueda.value).trim();
        pintar();
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
      /* dataset.idArchivo crea el atributo data-id-archivo: el selector CSS
         debe ir con guiones o nunca coincidira con el boton. */
      lista.addEventListener("click", function (evento) {
        var eliminar = evento.target.closest("[data-id-archivo]");
        if (eliminar) {
          eliminarCatalogo(eliminar);
          return;
        }
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

    /* Solicitud del cliente: un catalogo se puede eliminar incluso cuando ya
       fue procesado; la API tambien quita sus productos de la base y borra el
       original del disco. Se pide confirmacion porque no hay deshacer. */
    async function eliminarCatalogo(botonEliminar) {
      if (ocupacion()) return;
      var idArchivo = Number(botonEliminar.dataset.idArchivo);
      if (!idArchivo) return;

      var fila = botonEliminar.closest(".fuentes__archivo");
      var nodoNombre = fila ? fila.querySelector(".fuentes__nombre") : null;
      var nombre = nodoNombre && nodoNombre.textContent
        ? nodoNombre.textContent.trim()
        : "";
      var cargadas = 0;
      var historialEncontrado = historial.find(function (archivo) {
        return Number(archivo.id_archivo) === idArchivo;
      });
      if (historialEncontrado) cargadas = Number(historialEncontrado.filas_ok || 0);

      var descripcion = nombre
        ? "Se eliminará el catálogo «" + nombre + "»"
        : "Se eliminará el catálogo";
      if (cargadas > 0) {
        descripcion +=
          " junto con " + cargadas + " producto" + (cargadas === 1 ? "" : "s") +
          " que provienen de él";
      }
      descripcion +=
        ", incluso si ya fue procesado. Esta acción no se puede deshacer.";

      var proseguir = false;
      if (window.Swal && window.Swal.fire) {
        var confirmacion = await window.Swal.fire({
          icon: "warning",
          title: "¿Eliminar el catálogo?",
          text: descripcion,
          showCancelButton: true,
          confirmButtonText: "Eliminar catálogo",
          cancelButtonText: "Conservar",
          reverseButtons: true,
          focusCancel: true,
          buttonsStyling: false,
          customClass: {
            popup: "fipca-alerta",
            confirmButton: "btn-fipca",
            cancelButton: "btn-fipca btn-fipca--fantasma",
            actions: "fipca-alerta__acciones",
          },
        });
        proseguir = confirmacion.isConfirmed;
      } else if (window.confirm) {
        proseguir = window.confirm(descripcion);
      }
      if (!proseguir) return;

      eliminando = true;
      aviso("");
      actualizar();
      botonEliminar.disabled = true;

      try {
        var resultado = await Fipca.pedir(
          "/api/v1/inventario/archivos/" + idArchivo,
          { metodo: "DELETE" }
        );
        var unidad =
          resultado.productos_eliminados === 1 ? " producto" : " productos";
        await Fipca.aviso(
          null,
          "Catálogo eliminado junto con " +
            resultado.productos_eliminados + unidad + ".",
          "exito"
        );
      } catch (error) {
        aviso(error.message || "No se pudo eliminar el catálogo.");
      } finally {
        eliminando = false;
        await cargarHistorial();
        actualizar();
        var restantes = lista.querySelectorAll(".fuentes__eliminar");
        if (restantes.length) restantes[0].focus();
        else if (boton && !boton.disabled) boton.focus();
      }
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

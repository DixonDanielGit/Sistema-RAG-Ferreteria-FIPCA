/* Visor de la bitacora de auditoria (RF-05.2).
   La tabla es de solo lectura. Todo el texto del servidor se pinta con el
   renderizador de texto de DataTables, nunca como HTML. */
(function () {
  "use strict";

  var formulario = document.getElementById("form-filtros-bitacora");
  var tablaElemento = document.getElementById("tabla-bitacora");
  if (!formulario || !tablaElemento) return;

  var aviso = document.getElementById("aviso-bitacora");
  var conteo = document.getElementById("conteo-bitacora");
  var modulo = document.getElementById("filtro-modulo");
  var botonFiltrar = document.getElementById("filtrar-bitacora");
  var botonLimpiar = document.getElementById("limpiar-filtros");
  var tabla = null;
  var cargando = false;

  function texto(valor) {
    return valor === null || valor === undefined || valor === "" ? "—" : String(valor);
  }

  function fechaHora(evento) {
    var partes = String(evento.fecha || "").split("-");
    var fecha =
      partes.length === 3
        ? partes[2] + "/" + partes[1] + "/" + partes[0]
        : texto(evento.fecha);
    var hora = String(evento.hora || "").slice(0, 8);
    return (fecha + " " + hora).trim();
  }

  function usuarioVisible(evento) {
    if (evento.nombre_usuario) return evento.nombre_usuario;
    if (evento.id_usuario) return "Usuario #" + evento.id_usuario;
    return "No identificado";
  }

  function fila(evento) {
    return {
      fecha_hora: fechaHora(evento),
      fecha_orden: String(evento.fecha || "") + "T" + String(evento.hora || ""),
      usuario: usuarioVisible(evento),
      accion: texto(evento.accion),
      modulo: texto(evento.modulo),
      ip: texto(evento.ip),
    };
  }

  function columnas() {
    var renderTexto = window.jQuery.fn.dataTable.render.text();
    return [
      {
        data: null,
        render: function (_dato, tipo, evento) {
          return tipo === "display" ? evento.fecha_hora : evento.fecha_orden;
        },
      },
      { data: "usuario", render: renderTexto },
      { data: "accion", render: renderTexto },
      { data: "modulo", render: renderTexto },
      { data: "ip", render: renderTexto },
    ];
  }

  function inicializarTabla() {
    if (!window.jQuery || !window.jQuery.fn.DataTable) return null;
    return window.jQuery(tablaElemento).DataTable({
      data: [],
      columns: columnas(),
      autoWidth: false,
      deferRender: true,
      order: [[0, "desc"]],
      pageLength: 25,
      lengthMenu: [10, 25, 50, 100],
      language: {
        emptyTable: "No hay eventos para los filtros seleccionados.",
        info: "Mostrando _START_–_END_ de _TOTAL_ eventos",
        infoEmpty: "No hay eventos para mostrar",
        infoFiltered: "(filtrados de _MAX_ eventos)",
        lengthMenu: "Mostrar _MENU_",
        loadingRecords: "Cargando eventos…",
        processing: "Procesando…",
        search: "Buscar:",
        zeroRecords: "No hay eventos que coincidan con la búsqueda.",
        paginate: {
          first: "Primera",
          last: "Última",
          next: "Siguiente",
          previous: "Anterior",
        },
        aria: {
          sortAscending: ": activar para ordenar ascendentemente",
          sortDescending: ": activar para ordenar descendentemente",
        },
      },
      layout: {
        topStart: "pageLength",
        topEnd: "search",
        bottomStart: "info",
        bottomEnd: "paging",
      },
    });
  }

  function parametros() {
    var datos = new FormData(formulario);
    var params = new URLSearchParams();
    datos.forEach(function (valor, clave) {
      var limpio = String(valor || "").trim();
      if (limpio) params.set(clave, limpio);
    });
    return params;
  }

  function mostrarError(error) {
    window.Fipca.aviso(aviso, error.message, "error");
  }

  async function cargar() {
    if (cargando) return;
    cargando = true;
    if (botonFiltrar) botonFiltrar.disabled = true;
    tablaElemento.setAttribute("aria-busy", "true");
    if (conteo) conteo.textContent = "Cargando eventos…";

    var params = parametros();
    var limite = Number(params.get("limite") || 0);

    try {
      var eventos = await window.Fipca.pedir(
        "/api/v1/bitacora?" + params.toString()
      );
      if (tabla) {
        tabla.search("");
        tabla.clear();
        tabla.rows.add(eventos.map(fila));
        tabla.draw();
      }
      if (conteo) {
        var total = eventos.length;
        conteo.textContent =
          total === 0
            ? "No hay eventos para los filtros seleccionados."
            : total +
              (total === 1 ? " evento" : " eventos") +
              (limite && total >= limite ? " (límite alcanzado)" : "");
      }
    } catch (error) {
      mostrarError(error);
      if (conteo) conteo.textContent = "";
    } finally {
      cargando = false;
      if (botonFiltrar) botonFiltrar.disabled = false;
      tablaElemento.setAttribute("aria-busy", "false");
    }
  }

  async function cargarModulos() {
    if (!modulo) return;
    try {
      var modulos = await window.Fipca.pedir("/api/v1/bitacora/modulos");
      modulos.forEach(function (nombre) {
        var opcion = document.createElement("option");
        opcion.value = nombre;
        opcion.textContent = nombre;
        modulo.appendChild(opcion);
      });
    } catch (error) {
      /* El filtro queda en "Todos"; el visor sigue funcionando. */
    }
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    cargar();
  });

  if (botonLimpiar) {
    botonLimpiar.addEventListener("click", function () {
      formulario.reset();
      cargar();
    });
  }

  tabla = inicializarTabla();
  cargarModulos();
  cargar();
})();

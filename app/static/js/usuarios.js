/* Administracion de cuentas con modal y DataTables Responsive. */
import { inicializarValidacionFormulario } from "/static/js/expresionesRegulares.js";

(function () {
  "use strict";

  var tabla = document.getElementById("tabla-usuarios");
  if (!tabla) return;

  var lista = [];
  var conteo = document.getElementById("conteo-usuarios");
  var tablaDatos;
  var formulario = document.getElementById("form-usuario");
  var modalElemento = document.getElementById("modal-usuario");
  var modal = modalElemento
    ? window.bootstrap.Modal.getOrCreateInstance(modalElemento)
    : null;
  var campoPassword = document.getElementById("campo-password-inicial");
  var campoPasswordConf = document.getElementById(
    "campo-password-confirmacion"
  );
  var tituloModal = document.getElementById("modal-usuario-titulo");
  var ayudaModal = document.getElementById("modal-usuario-ayuda");
  var etiquetaGuardar = document.getElementById("guardar-usuario-etiqueta");
  var validador = formulario
    ? inicializarValidacionFormulario(formulario)
    : null;

  function escapar(valor) {
    return String(valor == null ? "" : valor).replace(
      /[&<>"']/g,
      function (caracter) {
        return {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[caracter];
      }
    );
  }

  function plantillaAcciones(usuario) {
    var accionEstado = usuario.activo ? "desactivar" : "activar";
    var textoEstado = usuario.activo ? "Desactivar" : "Activar";
    return [
      '<div class="cuenta-tabla__acciones">',
      '<button class="btn-fipca btn-fipca--fantasma" type="button" ',
      'data-accion="editar" data-id="' + usuario.id + '" ',
      'aria-label="Editar cuenta de ' +
        escapar(usuario.usuario) +
        '">Editar</button>',
      '<button class="btn-fipca btn-fipca--fantasma" type="button" ',
      'data-accion="' + accionEstado + '" data-id="' + usuario.id + '" ',
      'aria-label="' +
        textoEstado +
        " cuenta de " +
        escapar(usuario.usuario) +
        '">',
      textoEstado,
      "</button></div>",
    ].join("");
  }

  function columnas() {
    var texto = window.jQuery.fn.dataTable.render.text();
    return [
      {
        data: null,
        render: function (_dato, tipo, usuario) {
          var valor = usuario.nombre + " " + usuario.apellido;
          if (tipo !== "display") return valor;
          return "<strong>" + escapar(valor) + "</strong>";
        },
      },
      {
        data: null,
        render: function (_dato, tipo, usuario) {
          if (tipo !== "display") return usuario.usuario + " " + usuario.cedula;
          return (
            "<strong>" +
            escapar(usuario.usuario) +
            "</strong>" +
            '<span class="cuenta-tabla__secundario">' +
            escapar(usuario.cedula) +
            "</span>"
          );
        },
      },
      { data: "correo", render: texto },
      {
        data: "rol",
        render: function (valor, tipo) {
          if (tipo !== "display") return valor;
          return valor === "admin" ? "Administrador" : "Ventas";
        },
      },
      {
        data: "activo",
        render: function (activo, tipo) {
          if (tipo !== "display") return activo ? "Activa" : "Inactiva";
          return (
            '<span class="cuenta-estado ' +
            (activo ? "cuenta-estado--activo" : "cuenta-estado--inactivo") +
            '">' +
            (activo ? "Activa" : "Inactiva") +
            "</span>"
          );
        },
      },
      {
        data: null,
        orderable: false,
        searchable: false,
        render: function (_dato, tipo, usuario) {
          return tipo === "display" ? plantillaAcciones(usuario) : "";
        },
      },
    ];
  }

  function inicializarTabla() {
    tablaDatos = window.jQuery(tabla).DataTable({
      data: [],
      columns: columnas(),
      autoWidth: false,
      deferRender: true,
      createdRow: function (fila) {
        var encabezados = tabla.tHead && tabla.tHead.rows[0];
        if (!encabezados) return;
        Array.prototype.forEach.call(fila.cells, function (celda, indice) {
          var encabezado = encabezados.cells[indice];
          var etiqueta = encabezado ? encabezado.textContent.trim() : "";
          if (etiqueta) celda.setAttribute("data-label", etiqueta);
        });
      },
      order: [[0, "asc"]],
      pageLength: 10,
      lengthMenu: [10, 25, 50],
      language: {
        emptyTable: "Todavía no hay cuentas registradas.",
        info: "Mostrando _START_–_END_ de _TOTAL_ cuentas",
        infoEmpty: "No hay cuentas para mostrar",
        infoFiltered: "(filtradas de _MAX_ cuentas)",
        lengthMenu: "Mostrar _MENU_",
        loadingRecords: "Cargando cuentas…",
        processing: "Procesando…",
        search: "Buscar:",
        zeroRecords: "No hay cuentas que coincidan con la búsqueda.",
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
      drawCallback: function () {
        var informacion = this.api().page.info();
        conteo.textContent =
          informacion.recordsDisplay === informacion.recordsTotal
            ? informacion.recordsTotal +
              (informacion.recordsTotal === 1 ? " cuenta" : " cuentas")
            : informacion.recordsDisplay +
              " de " +
              informacion.recordsTotal +
              " cuentas";
      },
    });
  }

  function buscarCuenta(id) {
    return lista.find(function (usuario) {
      return String(usuario.id) === String(id);
    });
  }

  function configurarModo(edicion, usuario) {
    if (!formulario) return;

    formulario.reset();
    delete formulario.dataset.id;
    if (validador) validador.limpiar();

    if (edicion && usuario) {
      formulario.dataset.id = String(usuario.id);
      ["nombre", "apellido", "cedula", "usuario", "correo", "rol"].forEach(
        function (campo) {
          if (formulario.elements[campo]) {
            formulario.elements[campo].value = usuario[campo];
          }
        }
      );
    }

    if (campoPassword) campoPassword.hidden = edicion;
    if (campoPasswordConf) campoPasswordConf.hidden = edicion;
    formulario.elements.password.required = !edicion;
    formulario.elements.passwordConf.required = !edicion;

    if (tituloModal) {
      tituloModal.textContent = edicion ? "Editar usuario" : "Registrar usuario";
    }
    if (ayudaModal) {
      ayudaModal.textContent = edicion
        ? "Actualice los datos y el rol de acceso de esta cuenta."
        : "Complete los datos para dar de alta una nueva cuenta en el sistema.";
    }
    if (etiquetaGuardar) {
      etiquetaGuardar.textContent = edicion ? "Guardar cambios" : "Registrar";
    }
  }

  function abrirCreacion() {
    configurarModo(false);
    if (modal) modal.show();
  }

  function abrirEdicion(usuario) {
    configurarModo(true, usuario);
    if (modal) modal.show();
  }

  async function cargarUsuarios() {
    try {
      lista = await window.Fipca.pedir("/api/v1/auth/usuarios");
      tablaDatos.clear().rows.add(lista).draw();
    } catch (error) {
      tablaDatos.clear().draw();
      conteo.textContent = "No se pudieron cargar las cuentas.";
      await window.Fipca.aviso(null, error.message, "error");
    }
  }

  var botonAbrir = document.getElementById("abrir-modal-usuario");
  if (botonAbrir) {
    botonAbrir.addEventListener("click", abrirCreacion);
  }

  if (formulario) {
    formulario.addEventListener("submit", async function (evento) {
      evento.preventDefault();

      var esValido = validador ? validador.verificar() : true;
      if (!esValido) {
        await window.Fipca.aviso(
          null,
          "Por favor, complete correctamente los campos marcados antes de continuar.",
          "error"
        );
        return;
      }

      var id = formulario.dataset.id;
      var password = formulario.elements.password.value;
      var passwordConf = formulario.elements.passwordConf.value;
      if (!id && password !== passwordConf) {
        await window.Fipca.aviso(
          null,
          "Las contraseñas no coinciden.",
          "error"
        );
        return;
      }

      var boton = formulario.querySelector('button[type="submit"]');
      var giro = boton ? boton.querySelector(".spinner-border") : null;

      var datos = {
        cedula: formulario.elements.cedula.value.trim(),
        nombre: formulario.elements.nombre.value.trim(),
        apellido: formulario.elements.apellido.value.trim(),
        usuario: formulario.elements.usuario.value.trim(),
        correo: formulario.elements.correo.value.trim(),
        rol: formulario.elements.rol.value,
      };
      if (!id) datos.password = password;

      if (boton && giro) {
        window.Fipca.cargando(
          boton,
          giro,
          true,
          id ? "Guardando…" : "Registrando…"
        );
      }

      try {
        await window.Fipca.pedir(
          id
            ? "/api/v1/auth/usuarios/" + encodeURIComponent(id)
            : "/api/v1/auth/register",
          {
            metodo: id ? "PUT" : "POST",
            cuerpo: datos,
          }
        );

        if (modal) modal.hide();

        await window.Fipca.aviso(
          null,
          id
            ? "Los cambios de la cuenta se guardaron."
            : "La cuenta se creó correctamente.",
          "exito"
        );
        await cargarUsuarios();
      } catch (error) {
        await window.Fipca.aviso(null, error.message, "error");
      } finally {
        if (boton && giro) {
          window.Fipca.cargando(boton, giro, false);
        }
      }
    });

    if (modalElemento) {
      modalElemento.addEventListener("shown.bs.modal", function () {
        var campoInicial = formulario.querySelector(
          'input:not([type="hidden"]):not([disabled])'
        );
        if (campoInicial) campoInicial.focus();
      });
      modalElemento.addEventListener("hidden.bs.modal", function () {
        configurarModo(false);
      });
    }
  }

  tabla.addEventListener("click", async function (evento) {
    var boton = evento.target.closest("button[data-accion]");
    if (!boton) return;

    var cuenta = buscarCuenta(boton.dataset.id);
    if (!cuenta) return;
    if (boton.dataset.accion === "editar") {
      abrirEdicion(cuenta);
      return;
    }

    var activar = boton.dataset.accion === "activar";
    if (!activar) {
      var confirmacion = await window.Swal.fire({
        icon: "warning",
        title: "¿Desactivar esta cuenta?",
        text: "La persona no podrá iniciar sesión. Su historial se conservará.",
        showCancelButton: true,
        confirmButtonText: "Desactivar cuenta",
        cancelButtonText: "Cancelar",
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
      if (!confirmacion.isConfirmed) return;
    }

    boton.disabled = true;
    try {
      await window.Fipca.pedir(
        "/api/v1/auth/usuarios/" + encodeURIComponent(cuenta.id) + "/estado",
        { metodo: "PATCH", cuerpo: { activo: activar } }
      );
      await window.Fipca.aviso(
        null,
        activar ? "La cuenta se activó." : "La cuenta se desactivó.",
        "exito"
      );
      await cargarUsuarios();
    } catch (error) {
      await window.Fipca.aviso(null, error.message, "error");
    } finally {
      boton.disabled = false;
    }
  });

  inicializarTabla();
  cargarUsuarios();
})();

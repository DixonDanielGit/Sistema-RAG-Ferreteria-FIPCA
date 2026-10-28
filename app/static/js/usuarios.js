/* Administracion de cuentas con modal y DataTables Responsive. */
import {
  inicializarValidacionFormulario,
  limpiarValidacionFormulario,
} from "/static/js/expresionesRegulares.js";

(function () {
  "use strict";

  var tabla = document.getElementById("tabla-usuarios");
  if (!tabla) return;

  var lista = [];
  var conteo = document.getElementById("conteo-usuarios");
  var formularioEdicion = document.getElementById("form-usuario");
  var campoPasswordEdicion = document.getElementById("campo-password-inicial");
  var modalEdicionElemento = document.getElementById("modal-usuario");
  var modalEdicion = modalEdicionElemento
    ? window.bootstrap.Modal.getOrCreateInstance(modalEdicionElemento)
    : null;
  var tituloModalEdicion = document.getElementById("modal-usuario-titulo");
  var ayudaModalEdicion = document.getElementById("modal-usuario-ayuda");
  var etiquetaGuardarEdicion = document.getElementById(
    "guardar-usuario-etiqueta"
  );
  var tablaDatos;

  // Modal y formulario de Registro (con validaciones interactivas)
  var formRegistro = document.getElementById("form-usuario2");
  var modalRegistroElemento = document.getElementById("exampleModal");
  var modalRegistro = modalRegistroElemento
    ? window.bootstrap.Modal.getOrCreateInstance(modalRegistroElemento)
    : null;
  var validadorRegistro = formRegistro
    ? inicializarValidacionFormulario(formRegistro)
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
        responsivePriority: 2,
        render: function (_dato, tipo, usuario) {
          var valor = usuario.nombre + " " + usuario.apellido;
          if (tipo !== "display") return valor;
          return "<strong>" + escapar(valor) + "</strong>";
        },
      },
      {
        data: null,
        responsivePriority: 3,
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
      { data: "correo", render: texto, responsivePriority: 4 },
      {
        data: "rol",
        responsivePriority: 5,
        render: function (valor, tipo) {
          if (tipo !== "display") return valor;
          return valor === "admin" ? "Administrador" : "Ventas";
        },
      },
      {
        data: "activo",
        responsivePriority: 6,
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
        responsivePriority: 1,
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
      responsive: {
        details: {
          type: "inline",
          target: "tr",
        },
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

  function abrirCreacion() {
    if (formRegistro) {
      formRegistro.reset();
      if (validadorRegistro) {
        validadorRegistro.limpiar();
      }
    }
    if (modalRegistro) {
      modalRegistro.show();
    }
  }

  function abrirEdicion(usuario) {
    if (!formularioEdicion) return;
    formularioEdicion.reset();
    formularioEdicion.dataset.id = String(usuario.id);
    ["nombre", "apellido", "cedula", "usuario", "correo", "rol"].forEach(
      function (campo) {
        if (formularioEdicion.elements[campo]) {
          formularioEdicion.elements[campo].value = usuario[campo];
        }
      }
    );
    if (campoPasswordEdicion) {
      campoPasswordEdicion.hidden = true;
    }
    if (formularioEdicion.elements.password) {
      formularioEdicion.elements.password.required = false;
      formularioEdicion.elements.password.value = "";
    }
    if (tituloModalEdicion) {
      tituloModalEdicion.textContent = "Editar usuario";
    }
    if (ayudaModalEdicion) {
      ayudaModalEdicion.textContent =
        "Actualice los datos y el rol de acceso de esta cuenta.";
    }
    if (etiquetaGuardarEdicion) {
      etiquetaGuardarEdicion.textContent = "Guardar cambios";
    }
    if (modalEdicion) {
      modalEdicion.show();
    }
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

  // Enviar formulario de Registro (con validaciones dinámicas)
  if (formRegistro) {
    formRegistro.addEventListener("submit", async function (evento) {
      evento.preventDefault();

      // Verificar todas las validaciones antes de procesar
      var esValido = validadorRegistro ? validadorRegistro.verificar() : true;
      if (!esValido) {
        await window.Fipca.aviso(
          null,
          "Por favor, complete correctamente los campos marcados antes de continuar.",
          "error"
        );
        return;
      }

      var password = formRegistro.elements.password.value;
      var passwordConf = formRegistro.elements.passwordConf.value;
      if (password !== passwordConf) {
        await window.Fipca.aviso(
          null,
          "Las contraseñas no coinciden.",
          "error"
        );
        return;
      }

      var boton = formRegistro.querySelector('button[type="submit"]');
      var giro = boton ? boton.querySelector(".spinner-border") : null;

      var datos = {
        cedula: formRegistro.elements.cedula.value.trim(),
        nombre: formRegistro.elements.nombre.value.trim(),
        apellido: formRegistro.elements.apellido.value.trim(),
        usuario: formRegistro.elements.usuario.value.trim(),
        correo: formRegistro.elements.correo.value.trim(),
        password: password,
        rol: formRegistro.elements.rol.value,
      };

      if (boton && giro) {
        window.Fipca.cargando(boton, giro, true, "Registrando…");
      }

      try {
        await window.Fipca.pedir("/api/v1/auth/register", {
          metodo: "POST",
          cuerpo: datos,
        });

        if (modalRegistro) {
          modalRegistro.hide();
        }
        formRegistro.reset();
        if (validadorRegistro) {
          validadorRegistro.limpiar();
        }

        await window.Fipca.aviso(
          null,
          "La cuenta se creó correctamente.",
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

    if (modalRegistroElemento) {
      modalRegistroElemento.addEventListener("shown.bs.modal", function () {
        var primerInput = formRegistro.querySelector(
          'input:not([type="hidden"]):not([disabled])'
        );
        if (primerInput) primerInput.focus();
      });

      modalRegistroElemento.addEventListener("hidden.bs.modal", function () {
        formRegistro.reset();
        if (validadorRegistro) {
          validadorRegistro.limpiar();
        }
      });
    }
  }

  // Enviar formulario de Edición (modal-usuario)
  if (formularioEdicion) {
    formularioEdicion.addEventListener("submit", async function (evento) {
      evento.preventDefault();
      if (!formularioEdicion.reportValidity()) return;

      var boton = formularioEdicion.querySelector('button[type="submit"]');
      var giro = boton ? boton.querySelector(".spinner-border") : null;
      var id = formularioEdicion.dataset.id;
      var datos = {};
      new FormData(formularioEdicion).forEach(function (valor, clave) {
        datos[clave] = valor;
      });

      if (boton && giro) {
        window.Fipca.cargando(boton, giro, true, "Guardando…");
      }
      try {
        await window.Fipca.pedir(
          id
            ? "/api/v1/auth/usuarios/" + encodeURIComponent(id)
            : "/api/v1/auth/register",
          { metodo: id ? "PUT" : "POST", cuerpo: datos }
        );
        if (modalEdicion) {
          modalEdicion.hide();
        }
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

    if (modalEdicionElemento) {
      modalEdicionElemento.addEventListener("shown.bs.modal", function () {
        var campoInicial = formularioEdicion.querySelector(
          'input:not([type="hidden"]):not([disabled])'
        );
        if (campoInicial) campoInicial.focus();
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

/* Edicion del perfil y de la fotografia de la cuenta actual. */
import { inicializarValidacionFormulario } from "/static/js/expresionesRegulares.js";

(function () {
  "use strict";

  var form = document.getElementById("form-perfil");
  if (!form) return;
  var validador = inicializarValidacionFormulario(form);

  var modalElemento = document.getElementById("modal-perfil");
  var modal = window.bootstrap.Modal.getOrCreateInstance(modalElemento);
  var imagenes = [
    document.getElementById("imagen-perfil"),
    document.getElementById("vista-previa-imagen"),
  ];
  var campoArchivo = document.getElementById("archivo-perfil");
  var botonQuitar = document.getElementById("quitar-imagen");
  var notaImagen = document.getElementById("nota-imagen-perfil");
  var avatarPredeterminado = "/static/img/avatar-default.svg";
  var urlTemporal = null;
  var archivoSeleccionado = null;
  var fuenteGuardada = imagenes[0].getAttribute("src");
  var avisoValidacion =
    "Revise los campos marcados y corrija el formato antes de guardar.";

  function mostrarImagen(fuente) {
    imagenes.forEach(function (elemento) {
      elemento.src = fuente;
    });
  }

  function liberarVistaPrevia() {
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    urlTemporal = null;
    archivoSeleccionado = null;
    campoArchivo.value = "";
    mostrarImagen(fuenteGuardada);
    notaImagen.textContent = "La imagen seleccionada se guarda al confirmar los cambios.";
    notaImagen.removeAttribute("data-tipo");
  }

  imagenes.forEach(function (elemento) {
    elemento.addEventListener("error", function () {
      elemento.src = avatarPredeterminado;
    });
  });

  document.getElementById("abrir-modal-perfil").addEventListener("click", function () {
    modal.show();
  });

  form.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    if (!validador.verificar()) {
      await window.Fipca.aviso(null, avisoValidacion, "error");
      return;
    }

    var boton = form.querySelector('button[type="submit"]');
    var giro = boton.querySelector(".spinner-border");
    var datos = {};
    new FormData(form).forEach(function (valor, clave) {
      datos[clave] = valor;
    });

    window.Fipca.cargando(boton, giro, true, "Guardando…");
    try {
      var usuario = await window.Fipca.pedir("/api/v1/auth/me", {
        metodo: "PUT",
        cuerpo: datos,
      });

      ["nombre", "apellido", "cedula", "usuario", "correo"].forEach(function (campo) {
        form.elements[campo].value = usuario[campo];
      });
      document.getElementById("perfil-resumen-titulo").textContent =
        usuario.nombre + " " + usuario.apellido;
      document.getElementById("perfil-resumen-usuario").textContent = usuario.usuario;
      document.getElementById("perfil-resumen-cedula").textContent = usuario.cedula;
      document.getElementById("perfil-resumen-correo").textContent = usuario.correo;

      var nombreNav = document.querySelector(".fipca-nav__usuario strong");
      if (nombreNav) nombreNav.textContent = usuario.nombre + " " + usuario.apellido;

      if (archivoSeleccionado) {
        var datosImagen = new FormData();
        datosImagen.append("archivo", archivoSeleccionado);
        try {
          await window.Fipca.pedir("/api/v1/auth/me/imagen", {
            metodo: "POST",
            cuerpo: datosImagen,
          });
        } catch (errorImagen) {
          throw new Error(
            "Sus datos personales se guardaron, pero no se pudo actualizar la imagen: " +
              errorImagen.message
          );
        }
        fuenteGuardada = "/api/v1/auth/me/imagen?actualizado=" + Date.now();
        botonQuitar.hidden = false;
      }

      liberarVistaPrevia();
      validador.limpiar();
      modal.hide();
      await window.Fipca.aviso(null, "Los cambios del perfil se guardaron.", "exito");
    } catch (error) {
      await window.Fipca.aviso(null, error.message, "error");
    } finally {
      window.Fipca.cargando(boton, giro, false);
    }
  });

  campoArchivo.addEventListener("change", function () {
    archivoSeleccionado = campoArchivo.files && campoArchivo.files[0];
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    urlTemporal = null;
    if (!archivoSeleccionado) {
      mostrarImagen(fuenteGuardada);
      notaImagen.textContent = "La imagen seleccionada se guarda al confirmar los cambios.";
      notaImagen.removeAttribute("data-tipo");
      return;
    }
    if (archivoSeleccionado.size > 2 * 1024 * 1024) {
      archivoSeleccionado = null;
      campoArchivo.value = "";
      mostrarImagen(fuenteGuardada);
      notaImagen.textContent = "La imagen supera el límite de 2 MB.";
      notaImagen.setAttribute("data-tipo", "error");
      window.Fipca.aviso(null, "La imagen supera el límite de 2 MB.", "error");
      return;
    }
    var extensionesPorTipo = {
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      png: "image/png",
      webp: "image/webp",
    };
    var extensionImagen = archivoSeleccionado.name.split(".").pop().toLowerCase();
    var tipoEsperado = extensionesPorTipo[extensionImagen];
    if (
      !tipoEsperado ||
      (archivoSeleccionado.type && archivoSeleccionado.type !== tipoEsperado)
    ) {
      archivoSeleccionado = null;
      campoArchivo.value = "";
      mostrarImagen(fuenteGuardada);
      notaImagen.textContent = "Seleccione una imagen JPEG, PNG o WebP.";
      notaImagen.setAttribute("data-tipo", "error");
      window.Fipca.aviso(null, "Seleccione una imagen JPEG, PNG o WebP.", "error");
      return;
    }

    urlTemporal = URL.createObjectURL(archivoSeleccionado);
    mostrarImagen(urlTemporal);
    notaImagen.textContent = "Vista previa lista. Confirme para guardar la imagen.";
    notaImagen.setAttribute("data-tipo", "seleccionada");
  });

  botonQuitar.addEventListener("click", async function () {
    var confirmacion = await window.Swal.fire({
      icon: "warning",
      title: "¿Quitar la imagen de perfil?",
      text: "Se mostrará el avatar predeterminado.",
      showCancelButton: true,
      confirmButtonText: "Quitar imagen",
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

    botonQuitar.disabled = true;
    try {
      await window.Fipca.pedir("/api/v1/auth/me/imagen", {
        metodo: "DELETE",
        cuerpo: {},
      });
      if (urlTemporal) URL.revokeObjectURL(urlTemporal);
      urlTemporal = null;
      archivoSeleccionado = null;
      campoArchivo.value = "";
      fuenteGuardada = avatarPredeterminado;
      mostrarImagen(fuenteGuardada);
      botonQuitar.hidden = true;
      notaImagen.textContent = "Se usará el avatar predeterminado.";
      await window.Fipca.aviso(null, "Se quitó la imagen de perfil.", "exito");
    } catch (error) {
      await window.Fipca.aviso(null, error.message, "error");
    } finally {
      botonQuitar.disabled = false;
    }
  });

  modalElemento.addEventListener("shown.bs.modal", function () {
    var campoInicial = form.querySelector("input");
    if (campoInicial) campoInicial.focus();
  });

  modalElemento.addEventListener("hidden.bs.modal", function () {
    liberarVistaPrevia();
    validador.limpiar();
  });

  window.addEventListener("beforeunload", function () {
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
  });
})();

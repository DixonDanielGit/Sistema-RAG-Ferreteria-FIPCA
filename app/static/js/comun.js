/* Utilidades comunes de la interfaz web (Adenda 1).
   Sin dependencias: fetch + DOM del navegador. */
(function () {
  "use strict";

  var Fipca = {};
  var loaderVistas = document.getElementById("loader-vista");
  var temporizadorLoader;
  var alertaToast = window.Swal
    ? window.Swal.mixin({
        toast: true,
        position: "top-end",
        showConfirmButton: false,
        timer: 3600,
        timerProgressBar: true,
      })
    : null;

  Fipca.mostrarLoaderVista = function () {
    if (!loaderVistas) return;
    window.clearTimeout(temporizadorLoader);
    loaderVistas.hidden = false;
    document.body.setAttribute("aria-busy", "true");
  };

  function ocultarLoaderVista() {
    window.clearTimeout(temporizadorLoader);
    if (loaderVistas) loaderVistas.hidden = true;
    document.body.removeAttribute("aria-busy");
  }

  Fipca.navegar = function (destino, reemplazar) {
    Fipca.mostrarLoaderVista();
    if (reemplazar) {
      window.location.replace(destino);
    } else {
      window.location.assign(destino);
    }
  };

  if (loaderVistas && document.readyState !== "complete") {
    temporizadorLoader = window.setTimeout(Fipca.mostrarLoaderVista, 120);
    window.addEventListener("load", ocultarLoaderVista, { once: true });
  }

  window.addEventListener("pageshow", ocultarLoaderVista);

  var menu = document.getElementById("fipca-menu-enlaces");
  var botonMenu = document.getElementById("fipca-menu-toggle");
  if (menu && botonMenu) {
    var barraNavegacion = botonMenu.closest(".fipca-nav");
    var puntoQuiebreMenu = window.matchMedia("(max-width: 1150px)");

    function cerrarMenu() {
      menu.hidden = true;
      botonMenu.setAttribute("aria-expanded", "false");
      botonMenu.setAttribute("aria-label", "Abrir navegación");
      botonMenu.title = "Abrir navegación";
      if (barraNavegacion) barraNavegacion.classList.remove("fipca-nav--menu-abierto");
    }

    function actualizarMenuPorAncho() {
      if (puntoQuiebreMenu.matches) {
        botonMenu.hidden = false;
        cerrarMenu();
      } else {
        botonMenu.hidden = true;
        menu.hidden = false;
        if (barraNavegacion) {
          barraNavegacion.classList.remove("fipca-nav--menu-abierto");
        }
      }
    }

    botonMenu.addEventListener("click", function () {
      var abierto = botonMenu.getAttribute("aria-expanded") === "true";
      if (abierto) {
        cerrarMenu();
      } else {
        menu.hidden = false;
        botonMenu.setAttribute("aria-expanded", "true");
        botonMenu.setAttribute("aria-label", "Cerrar navegación");
        botonMenu.title = "Cerrar navegación";
        if (barraNavegacion) barraNavegacion.classList.add("fipca-nav--menu-abierto");
        var primerEnlace = menu.querySelector("a[href]");
        if (primerEnlace) primerEnlace.focus();
      }
    });

    menu.addEventListener("click", function (evento) {
      if (evento.target.closest("a[href]") && puntoQuiebreMenu.matches) {
        cerrarMenu();
      }
    });

    document.addEventListener("click", function (evento) {
      if (puntoQuiebreMenu.matches &&
          !botonMenu.contains(evento.target) &&
          !menu.contains(evento.target)) {
        cerrarMenu();
      }
    });

    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && botonMenu.getAttribute("aria-expanded") === "true") {
        cerrarMenu();
        botonMenu.focus();
      }
    });

    if (puntoQuiebreMenu.addEventListener) {
      puntoQuiebreMenu.addEventListener("change", actualizarMenuPorAncho);
    } else {
      puntoQuiebreMenu.addListener(actualizarMenuPorAncho);
    }
    actualizarMenuPorAncho();
  }

  /** Token CSRF publicado en el <head> por la plantilla. */
  Fipca.csrf = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  };

  /**
   * Peticion JSON a la API.
   * - Adjunta la cookie de sesion (misma origen) y la cabecera CSRF.
   * - Si la sesion expiro (401) manda al login, salvo que se pida lo contrario.
   */
  Fipca.pedir = async function (ruta, opciones) {
    opciones = opciones || {};
    var cabeceras = Object.assign(
      { Accept: "application/json" },
      opciones.cabeceras || {}
    );
    var configuracion = {
      method: opciones.metodo || "GET",
      headers: cabeceras,
      credentials: "same-origin",
      cache: "no-store",
    };

    if (opciones.cuerpo !== undefined) {
      cabeceras["X-CSRF-Token"] = Fipca.csrf();
      if (opciones.cuerpo instanceof FormData) {
        configuracion.body = opciones.cuerpo;
      } else {
        cabeceras["Content-Type"] = "application/json";
        configuracion.body = JSON.stringify(opciones.cuerpo);
      }
    }

    var respuesta;
    try {
      respuesta = await fetch(ruta, configuracion);
    } catch (error) {
      throw new Error("No se pudo contactar con el servidor. Verifique su conexion.");
    }

    var datos = {};
    try {
      datos = await respuesta.json();
    } catch (error) {
      datos = {};
    }

    if (respuesta.status === 401 && !opciones.noRedirigir) {
      Fipca.navegar("/login?expirada=1");
      throw new Error("Sesion expirada");
    }

    if (!respuesta.ok) {
      var detalle = datos.detail;
      if (Array.isArray(detalle)) {
        detalle = detalle
          .map(function (item) {
            return item.msg || "Dato invalido";
          })
          .join(". ");
      }
      var fallo = new Error(detalle || "Ocurrio un error inesperado.");
      fallo.estado = respuesta.status;
      fallo.datos = datos;
      throw fallo;
    }

    return datos;
  };

  /** Muestra u oculta el bloque de aviso. */
  Fipca.aviso = function (elemento, mensaje, tipo) {
    if (!mensaje) {
      if (elemento) {
        elemento.hidden = true;
        elemento.textContent = "";
      }
      return Promise.resolve();
    }
    if (!window.Swal || !alertaToast) {
      console.error("SweetAlert2 no esta disponible; no se pudo mostrar el aviso.");
      return Promise.reject(new Error("No se pudo cargar el sistema de alertas."));
    }

    var clase = tipo === "exito" ? "success" : tipo === "info" ? "info" : "error";
    if (clase === "error") {
      return window.Swal.fire({
        icon: clase,
        title: "No se pudo completar",
        text: mensaje,
        confirmButtonText: "Entendido",
        buttonsStyling: false,
        customClass: {
          popup: "fipca-alerta",
          confirmButton: "btn-fipca",
        },
      });
    }
    return alertaToast.fire({
      icon: clase,
      title: mensaje,
      customClass: { popup: "fipca-alerta fipca-alerta--toast" },
    });
  };

  /** Marca o limpia el error de un campo. */
  Fipca.errorCampo = function (entrada, texto) {
    if (!entrada) return;
    var identificador = entrada.getAttribute("aria-describedby") || "";
    var parrafo = document.getElementById(
      identificador.split(" ").filter(function (id) {
        return id.indexOf("error-") === 0;
      })[0] || ""
    );
    if (texto) {
      entrada.setAttribute("aria-invalid", "true");
      if (parrafo) parrafo.textContent = texto;
    } else {
      entrada.removeAttribute("aria-invalid");
      if (parrafo) parrafo.textContent = "";
    }
  };

  /** Alterna el estado de carga de un boton con spinner. */
  Fipca.cargando = function (boton, giro, activo, textoOcupado) {
    if (!boton) return;
    boton.disabled = activo;
    if (giro) giro.hidden = !activo;
    if (textoOcupado) {
      var etiqueta = boton.querySelector("span:last-child");
      if (!boton.dataset.textoOriginal) {
        boton.dataset.textoOriginal = etiqueta ? etiqueta.textContent : "";
      }
      if (etiqueta) {
        etiqueta.textContent = activo ? textoOcupado : boton.dataset.textoOriginal;
      }
    }
  };

  /** Confirma el cierre de sesion, la registra y vuelve al login. */
  Fipca.cerrarSesion = async function (boton) {
    if (boton) boton.disabled = true;
    var confirmacion = await window.Swal.fire({
      icon: "question",
      title: "¿Desea cerrar la sesión?",
      text: "Tendrá que ingresar nuevamente para volver al sistema.",
      showCancelButton: true,
      confirmButtonText: "Cerrar sesión",
      cancelButtonText: "Seguir aquí",
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
    if (!confirmacion.isConfirmed) {
      if (boton) boton.disabled = false;
      return;
    }

    try {
      await Fipca.pedir("/api/v1/auth/logout", { metodo: "POST", cuerpo: {} });
    } catch (error) {
      if (error.estado === 401) {
        Fipca.navegar("/login?expirada=1", true);
        return;
      }
      if (boton) boton.disabled = false;
      await Fipca.aviso(null, error.message, "error");
      return;
    }
    Fipca.navegar("/login?salida=1");
  };

  /* ---------------------------- Inicializacion ---------------------------- */

  document.addEventListener("click", function (evento) {
    if (evento.defaultPrevented || evento.button !== 0 ||
        evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) {
      return;
    }

    var origen = evento.target;
    if (!(origen instanceof Element)) return;
    var enlace = origen.closest("a[href]");
    if (!enlace || enlace.hasAttribute("download") ||
        (enlace.target && enlace.target.toLowerCase() !== "_self") ||
        enlace.relList.contains("external")) {
      return;
    }

    var destino = new URL(enlace.href, window.location.href);
    if (destino.origin !== window.location.origin ||
        !["http:", "https:"].includes(destino.protocol) ||
        (destino.hash && destino.pathname === window.location.pathname &&
          destino.search === window.location.search)) {
      return;
    }

    Fipca.mostrarLoaderVista();
  });

  document.addEventListener("click", function (evento) {
    var salir = evento.target.closest("[data-cerrar-sesion]");
    if (salir) {
      evento.preventDefault();
      Fipca.cerrarSesion(salir);
      return;
    }

    var ver = evento.target.closest("[data-ver-password]");
    if (ver) {
      var campo = ver.parentElement.querySelector("input");
      if (!campo) return;
      var oculto = campo.type === "password";
      campo.type = oculto ? "text" : "password";
      ver.setAttribute("aria-pressed", String(oculto));
      ver.setAttribute(
        "aria-label",
        oculto ? "Ocultar contrasena" : "Mostrar contrasena"
      );
    }
  });

  window.Fipca = Fipca;
})();

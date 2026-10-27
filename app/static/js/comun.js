/* Utilidades comunes de la interfaz web (Adenda 1).
   Sin dependencias: fetch + DOM del navegador. */
(function () {
  "use strict";

  var Fipca = {};

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
      window.location.href = "/login?expirada=1";
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
    if (!elemento) return;
    if (!mensaje) {
      elemento.hidden = true;
      elemento.textContent = "";
      return;
    }
    elemento.hidden = false;
    elemento.setAttribute("data-tipo", tipo || "error");
    elemento.textContent = mensaje;
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

  /** Cierra la sesion en el servidor y vuelve al login. */
  Fipca.cerrarSesion = async function () {
    try {
      await Fipca.pedir("/api/v1/auth/logout", { metodo: "POST", cuerpo: {} });
    } catch (error) {
      // Si el token ya no sirve, igual se sale: el servidor borra las cookies.
    }
    window.location.href = "/login?salida=1";
  };

  /* ---------------------------- Inicializacion ---------------------------- */

  document.addEventListener("click", function (evento) {
    var salir = evento.target.closest("[data-cerrar-sesion]");
    if (salir) {
      evento.preventDefault();
      salir.disabled = true;
      Fipca.cerrarSesion();
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

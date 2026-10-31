/* Vista del asistente (Adenda 1).
   Todo el texto que llega del servidor se pinta con textContent: si el modelo
   devolviera HTML o un producto tuviera un nombre malicioso, se ve como texto
   y nunca se ejecuta. Es la mitad del cliente del anti-prompt-injection. */
(function () {
  "use strict";

  var LIMITE = 2000;

  /* Mantiene mensajes de validacion especificos; traduce estados tecnicos
     como permisos y limites a instrucciones utiles para la persona. */
  function motivoDeFallo(error) {
    if (error.estado === 403) {
      return "La sesión cambió o la página quedó desactualizada. Recargue e intente de nuevo.";
    }
    if (error.estado === 429) {
      return "Se enviaron demasiadas consultas seguidas. Espere un momento antes de reintentar.";
    }
    if (error.estado === 422) {
      return error.message;
    }
    return "No se pudo contactar con el servidor. Revise su conexión e intente de nuevo.";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.getElementById("form-chat");
    if (!formulario) return;

    var hilo = document.getElementById("hilo-ancho");
    var vacio = document.getElementById("vacio");
    var entrada = document.getElementById("pregunta");
    var boton = document.getElementById("btn-enviar");
    var contador = document.getElementById("contador-chat");
    var errorChat = document.getElementById("error-chat");
    var enviando = false;
    var preguntaInteractuada = false;

    function alFinal() {
      var zona = document.getElementById("hilo");
      zona.scrollTop = zona.scrollHeight;
    }

    function ajustarAltura() {
      entrada.style.height = "auto";
      entrada.style.height = Math.min(entrada.scrollHeight, 160) + "px";
    }

    function actualizarEstado() {
      var largo = entrada.value.length;
      contador.textContent = largo + " / " + LIMITE;
      var valida = validarPregunta(preguntaInteractuada);
      boton.disabled = enviando || !valida;
      contador.style.color =
        largo > LIMITE * 0.9 ? "var(--ciruela-texto)" : "var(--texto-suave)";
    }

    function validarPregunta(mostrarVacio) {
      var valor = entrada.value;
      var mensaje = "";
      if (!valor.trim()) {
        if (mostrarVacio) mensaje = "Escriba una pregunta antes de enviarla.";
      } else if (valor.length > LIMITE) {
        mensaje = "La pregunta no puede superar los " + LIMITE + " caracteres.";
      } else if (valor.includes("\0")) {
        mensaje = "La pregunta contiene caracteres no permitidos.";
      }
      Fipca.errorCampo(entrada, mensaje);
      return !mensaje && Boolean(valor.trim());
    }

    function burbuja(rol, texto) {
      var mensaje = document.createElement("div");
      mensaje.className = "chat__mensaje chat__mensaje--" + rol;

      var avatar = document.createElement("span");
      avatar.className = "chat__avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = rol === "usuario" ? "Yo" : "IA";

      var cuerpo = document.createElement("div");
      cuerpo.className = "chat__burbuja";
      cuerpo.textContent = texto;

      mensaje.appendChild(avatar);
      mensaje.appendChild(cuerpo);
      if (vacio) vacio.hidden = true;
      hilo.appendChild(mensaje);
      alFinal();
      return cuerpo;
    }

    function tarjetasFuentes(destino, fuentes) {
      if (!Array.isArray(fuentes) || fuentes.length === 0) return;

      var caja = document.createElement("div");
      caja.className = "chat__fuentes";

      fuentes.forEach(function (producto) {
        var tarjeta = document.createElement("div");
        tarjeta.className = "chat__fuente";

        var nombre = document.createElement("strong");
        nombre.textContent = producto.nombre || "Producto";
        tarjeta.appendChild(nombre);

        var precio = document.createElement("span");
        var valor = Number(producto.precio);
        precio.textContent = isNaN(valor)
          ? "Precio no disponible"
          : "$ " + valor.toFixed(2);
        tarjeta.appendChild(precio);

        var stock = document.createElement("span");
        stock.textContent = "Stock: " + (producto.stock ?? 0) + " unidades";
        tarjeta.appendChild(stock);

        if (producto.codigo) {
          var codigo = document.createElement("span");
          codigo.textContent = "Codigo: " + producto.codigo;
          tarjeta.appendChild(codigo);
        }

        caja.appendChild(tarjeta);
      });

      destino.appendChild(caja);
    }

    function indicadorEscritura() {
      var mensaje = document.createElement("div");
      mensaje.className = "chat__mensaje chat__mensaje--asistente";
      mensaje.id = "escribiendo";

      var avatar = document.createElement("span");
      avatar.className = "chat__avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = "IA";

      var caja = document.createElement("div");
      caja.className = "chat__escribiendo";

      var giro = document.createElement("span");
      giro.className = "chat__giro";
      giro.setAttribute("aria-hidden", "true");

      var texto = document.createElement("span");
      texto.textContent = "Consultando el catálogo…";

      caja.appendChild(giro);
      caja.appendChild(texto);

      mensaje.appendChild(avatar);
      mensaje.appendChild(caja);
      hilo.appendChild(mensaje);
      alFinal();
      return mensaje;
    }

    async function preguntar(texto) {
      if (enviando) return;

      enviando = true;
      actualizarEstado();
      Fipca.aviso(errorChat, "");
      burbuja("usuario", texto);

      entrada.value = "";
      preguntaInteractuada = false;
      Fipca.errorCampo(entrada, "");
      ajustarAltura();
      actualizarEstado();

      var espera = indicadorEscritura();

      try {
        var datos = await Fipca.pedir("/api/v1/rag/chat", {
          metodo: "POST",
          cuerpo: { pregunta: texto },
        });
        espera.remove();
        var cuerpo = burbuja("asistente", datos.respuesta || "");

        if (datos.aviso) {
          var nota = document.createElement("p");
          nota.className = "chat__nota";
          nota.textContent = datos.aviso;
          cuerpo.appendChild(nota);
        }

        tarjetasFuentes(cuerpo, datos.fuentes);
      } catch (error) {
        espera.remove();
        burbuja(
          "asistente",
          "No se pudo obtener la respuesta. Intente de nuevo en unos segundos."
        );
        Fipca.aviso(errorChat, motivoDeFallo(error), "error");
      } finally {
        enviando = false;
        actualizarEstado();
        entrada.focus();
      }
    }

    formulario.addEventListener("submit", function (evento) {
      evento.preventDefault();
      var texto = entrada.value.trim();
      preguntaInteractuada = true;
      if (!validarPregunta(true)) {
        entrada.focus();
        return;
      }
      preguntar(texto);
    });

    entrada.addEventListener("input", function () {
      preguntaInteractuada = true;
      ajustarAltura();
      actualizarEstado();
    });

    entrada.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter" && !evento.shiftKey) {
        evento.preventDefault();
        formulario.requestSubmit();
      }
    });

    document.querySelectorAll("[data-pregunta]").forEach(function (sugerencia) {
      sugerencia.addEventListener("click", function () {
        entrada.value = sugerencia.getAttribute("data-pregunta") || "";
        ajustarAltura();
        actualizarEstado();
        formulario.requestSubmit();
      });
    });

    ajustarAltura();
    actualizarEstado();
    entrada.focus();

    /* La banda de consulta del panel llega con la pregunta en la URL: se envia
       sola y se limpia la barra de direcciones para que recargar no la repita. */
    var inicial = (new URLSearchParams(window.location.search).get("pregunta") || "").trim();
    if (inicial) {
      window.history.replaceState({}, "", "/chat");
      preguntar(inicial.slice(0, LIMITE));
    }
  });
})();

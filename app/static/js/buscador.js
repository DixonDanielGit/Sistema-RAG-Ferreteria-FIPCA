/* Buscador comercial (RF-03): consulta local a PostgreSQL.
   No hay IA en esta vista: el servidor responde con Full-Text Search y aqui
   solo se pintan los productos con textContent, nunca con HTML, para que un
   nombre raro del catalogo se muestre como texto y jamas se ejecute. */
(function () {
  "use strict";

  /* Minimo para buscar mientras se teclea; el envio manual del formulario
     baja a 2 porque asi lo acepta el servidor. */
  var MINIMO_TECLEO = 3;
  var MINIMO_ENVIO = 2;
  var RETRASO_MS = 350;
  var LIMITE = 50;

  var formulario = document.getElementById("form-buscador");
  var entrada = document.getElementById("consulta-buscador");
  if (!formulario || !entrada) return;

  var error = document.getElementById("error-buscador");
  var resumen = document.getElementById("resumen-buscador");
  var contenedor = document.getElementById("contenedor-resultados");
  var filas = document.getElementById("filas-buscador");
  var vacio = document.getElementById("buscador-vacio");
  var tituloVacio = document.getElementById("titulo-vacio-buscador");
  var textoVacio = document.getElementById("texto-vacio-buscador");
  var cargando = document.getElementById("cargando-buscador");

  var tituloInicial = tituloVacio ? tituloVacio.textContent.trim() : "";
  var textoInicial = textoVacio ? textoVacio.textContent.trim() : "";

  var temporizador = null;
  /* Numero de peticion: si llega una respuesta de una consulta que ya no es
     la vigente, se descarta y no pisa los resultados actuales. */
  var peticion = 0;

  function mostrar(nodo) {
    if (nodo) nodo.hidden = false;
  }

  function ocultar(nodo) {
    if (nodo) nodo.hidden = true;
  }

  function mostrarError(mensaje) {
    if (!error) return;
    if (!mensaje) {
      error.textContent = "";
      error.hidden = true;
      return;
    }
    error.textContent = mensaje;
    error.hidden = false;
  }

  /* Traduce los estados tecnicos a instrucciones utiles; los mensajes que
     llegan del servidor se muestran tal cual, como en el resto del sistema. */
  function motivoDeFallo(falla) {
    if (falla && falla.estado === 403) {
      return "La sesión cambió o la página quedó desactualizada. Recargue e intente de nuevo.";
    }
    if (falla && falla.estado === 429) {
      return "Se enviaron demasiadas consultas seguidas. Espere un momento antes de reintentar.";
    }
    return (
      (falla && falla.message) || "No se pudo consultar el catálogo. Intente de nuevo."
    );
  }

  function fijarVacio(titulo, texto) {
    if (tituloVacio) tituloVacio.textContent = titulo;
    if (textoVacio) textoVacio.textContent = texto;
    mostrar(vacio);
    ocultar(contenedor);
  }

  function mostrarReposo() {
    ocultar(cargando);
    ocultar(resumen);
    mostrarError("");
    fijarVacio(tituloInicial, textoInicial);
  }

  function formatearPrecio(valor, moneda) {
    var codigo = moneda || "USD";
    var cantidad = Number(valor);
    if (isNaN(cantidad)) cantidad = 0;
    try {
      return new Intl.NumberFormat("es-VE", {
        style: "currency",
        currency: codigo,
        minimumFractionDigits: 2,
      }).format(cantidad);
    } catch (falla) {
      return cantidad.toFixed(2) + " " + codigo;
    }
  }

  function resumenDe(datos, milisegundos) {
    var total = Number(datos.total) || 0;
    var lista = datos.productos || [];
    var texto =
      total === 1
        ? "1 producto encontrado"
        : total + " productos encontrados";
    texto += " en " + milisegundos + " ms.";
    if (total > lista.length) {
      texto += " Mostrando los primeros " + lista.length + ".";
    }
    return texto;
  }

  function crearCelda(clase) {
    var celda = document.createElement("td");
    if (clase) celda.className = clase;
    return celda;
  }

  function agregarDetalle(contenedor, clases, texto) {
    if (!texto) return;
    var nodo = document.createElement("span");
    nodo.className = clases;
    nodo.textContent = texto;
    contenedor.appendChild(nodo);
  }

  function filaProducto(producto) {
    var fila = document.createElement("tr");

    var codigo = crearCelda("buscador__codigo");
    if (producto.codigo) {
      var textoCodigo = document.createElement("code");
      textoCodigo.textContent = producto.codigo;
      codigo.appendChild(textoCodigo);
    }
    fila.appendChild(codigo);

    var celdaProducto = crearCelda("buscador__producto");
    var nombre = document.createElement("strong");
    nombre.className = "buscador__nombre";
    nombre.textContent = producto.nombre || "Sin nombre registrado";
    celdaProducto.appendChild(nombre);
    agregarDetalle(
      celdaProducto,
      "buscador__detalle",
      [producto.marca, producto.categoria, producto.presentacion]
        .filter(Boolean)
        .join(" · ")
    );
    agregarDetalle(
      celdaProducto,
      "buscador__descripcion",
      producto.descripcion && producto.descripcion.length > 180
        ? producto.descripcion.slice(0, 179) + "…"
        : producto.descripcion
    );
    fila.appendChild(celdaProducto);

    var proveedor = crearCelda("buscador__proveedor");
    proveedor.textContent = producto.proveedor || "Sin proveedor registrado";
    fila.appendChild(proveedor);

    var precio = crearCelda("buscador__precio");
    precio.appendChild(
      document.createTextNode(formatearPrecio(producto.precio, producto.moneda))
    );
    if (Number(producto.iva) > 0) {
      agregarDetalle(precio, "buscador__impuesto", "IVA " + Number(producto.iva) + " %");
    }
    if (Number(producto.descuentos) > 0) {
      agregarDetalle(
        precio,
        "buscador__descuento",
        "Descuento " + Number(producto.descuentos) + " %"
      );
    }
    fila.appendChild(precio);

    var stock = crearCelda("buscador__stock");
    var existencias = Number(producto.stock);
    stock.textContent = String(isNaN(existencias) ? 0 : existencias);
    stock.setAttribute(
      "data-agotado",
      isNaN(existencias) || existencias <= 0 ? "1" : ""
    );
    fila.appendChild(stock);

    return fila;
  }

  function pintarResultados(datos, milisegundos) {
    var lista = datos.productos || [];
    filas.textContent = "";
    lista.forEach(function (producto) {
      filas.appendChild(filaProducto(producto));
    });
    mostrar(contenedor);
    ocultar(vacio);
    mostrar(resumen);
    resumen.textContent = resumenDe(datos, milisegundos);
  }

  function pintarSinCoincidencias(datos, milisegundos, consulta) {
    ocultar(contenedor);
    mostrar(resumen);
    resumen.textContent = resumenDe(datos, milisegundos);
    fijarVacio(
      "Sin coincidencias",
      "No hay productos en el catálogo que coincidan con «" +
        consulta +
        "». Revise la ortografía o pruebe con una palabra más corta, " +
        "por ejemplo el código o la marca."
    );
  }

  function buscar(consulta) {
    var numero = ++peticion;
    mostrarError("");
    mostrar(cargando);
    var inicio = Date.now();

    Fipca.pedir(
      "/api/v1/inventario/busqueda?limite=" +
        LIMITE +
        "&consulta=" +
        encodeURIComponent(consulta)
    )
      .then(function (datos) {
        if (numero !== peticion) return;
        ocultar(cargando);
        var milisegundos = Math.max(1, Date.now() - inicio);
        if (!datos.productos || datos.productos.length === 0) {
          pintarSinCoincidencias(datos, milisegundos, consulta);
          return;
        }
        pintarResultados(datos, milisegundos);
      })
      .catch(function (falla) {
        if (numero !== peticion) return;
        ocultar(cargando);
        mostrarError(motivoDeFallo(falla));
      });
  }

  function cancelarPendiente() {
    if (temporizador) {
      clearTimeout(temporizador);
      temporizador = null;
    }
  }

  function programar(consulta) {
    cancelarPendiente();
    temporizador = setTimeout(function () {
      temporizador = null;
      buscar(consulta);
    }, RETRASO_MS);
  }

  entrada.addEventListener("input", function () {
    var consulta = entrada.value.trim();
    cancelarPendiente();
    if (consulta.length < MINIMO_TECLEO) {
      /* Al acortar la consulta ninguna respuesta en vuelo sigue vigente. */
      peticion += 1;
      mostrarReposo();
      return;
    }
    programar(consulta);
  });

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    var consulta = entrada.value.trim();
    if (consulta.length < MINIMO_ENVIO) {
      mostrarError("Escriba al menos " + MINIMO_ENVIO + " caracteres para buscar.");
      entrada.focus();
      return;
    }
    cancelarPendiente();
    buscar(consulta);
  });

  document.querySelectorAll("[data-buscar]").forEach(function (atajo) {
    atajo.addEventListener("click", function () {
      entrada.value = atajo.getAttribute("data-buscar") || "";
      cancelarPendiente();
      buscar(entrada.value.trim());
      entrada.focus();
    });
  });

  /* Sincroniza el estado accesible del boton que oculta el panel en
     escritorio. fuentes.js hace la alternancia y va cargado antes que este
     archivo, por lo que al llegar aqui el panel ya cambio de estado. */
  var alternar = document.getElementById("alternar-fuentes-pc");
  var panelFuentes = document.getElementById("panel-fuentes");
  if (alternar && panelFuentes) {
    alternar.addEventListener("click", function () {
      var visible = !panelFuentes.hidden;
      alternar.setAttribute("aria-expanded", String(visible));
      alternar.setAttribute(
        "aria-label",
        (visible ? "Ocultar" : "Mostrar") + " panel de fuentes"
      );
    });
  }
})();

/* Buscador comercial (RF-03): consulta local a PostgreSQL.
   No hay IA en esta vista: el servidor responde con Full-Text Search y aqui
   solo se pintan los productos con textContent, nunca con HTML, para que un
   nombre raro del catalogo se muestre como texto y jamas se ejecute. */
(function () {
  "use strict";

  var MINIMO_BUSQUEDA = 1;
  var RETRASO_MS = 350;
  var LIMITE = 25;

  var formulario = document.getElementById("form-buscador");
  var entrada = document.getElementById("consulta-buscador");
  if (!formulario || !entrada) return;

  var error = document.getElementById("error-buscador");
  var resumen = document.getElementById("resumen-buscador");
  var contenedor = document.getElementById("contenedor-resultados");
  var filas = document.getElementById("filas-buscador");
  var tarjetas = document.getElementById("tarjetas-buscador");
  var ordenMovil = document.getElementById("orden-movil-buscador");
  var vacio = document.getElementById("buscador-vacio");
  var tituloVacio = document.getElementById("titulo-vacio-buscador");
  var textoVacio = document.getElementById("texto-vacio-buscador");
  var cargando = document.getElementById("cargando-buscador");
  var botonCatalogo = document.getElementById("boton-ver-catalogo");
  var paginacion = document.getElementById("paginacion-catalogo");
  var anteriorCatalogo = document.getElementById("pagina-anterior-catalogo");
  var siguienteCatalogo = document.getElementById("pagina-siguiente-catalogo");
  var estadoPaginacion = document.getElementById("estado-paginacion-catalogo");
  var limiteResultados = document.getElementById("limite-resultados-buscador");
  var dialogoDetalle = document.getElementById("dialogo-detalle-producto");
  var cerrarDetalle = document.getElementById("cerrar-detalle-producto");
  var estadoDetalle = document.getElementById("estado-detalle-producto");
  var errorDetalle = document.getElementById("error-detalle-producto");
  var contenidoDetalle = document.getElementById("contenido-detalle-producto");
  var tituloDetalle = document.getElementById("titulo-detalle-producto");
  var datosProducto = document.getElementById("datos-detalle-producto");
  var datosProveedor = document.getElementById("datos-detalle-proveedor");
  var datosCatalogo = document.getElementById("datos-detalle-catalogo");
  var ofertasProducto = document.getElementById("ofertas-detalle-producto");

  var tituloInicial = tituloVacio ? tituloVacio.textContent.trim() : "";
  var textoInicial = textoVacio ? textoVacio.textContent.trim() : "";

  var temporizador = null;
  var paginaActual = 1;
  var totalActual = 0;
  var modoCatalogo = false;
  var ordenarPor = null;
  var direccionOrden = "asc";
  var solicitudDetalle = 0;
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
    ocultar(paginacion);
    modoCatalogo = false;
    if (botonCatalogo) botonCatalogo.disabled = false;
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
    var texto =
      total === 1
        ? "1 producto encontrado"
        : total + " productos encontrados";
    texto += " en " + milisegundos + " ms.";
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

  function agregarCampo(lista, etiqueta, valor) {
    if (valor === null || valor === undefined || valor === "") return;
    var termino = document.createElement("dt");
    termino.textContent = etiqueta;
    var definicion = document.createElement("dd");
    definicion.textContent = String(valor);
    lista.appendChild(termino);
    lista.appendChild(definicion);
  }

  function fechaLocal(valor, soloFecha) {
    if (!valor) return "No registrado";
    var fecha;
    if (soloFecha && /^\d{4}-\d{2}-\d{2}$/.test(valor)) {
      var partes = valor.split("-");
      fecha = new Date(Number(partes[0]), Number(partes[1]) - 1, Number(partes[2]));
    } else {
      fecha = new Date(valor);
    }
    if (isNaN(fecha.getTime())) return String(valor);
    return new Intl.DateTimeFormat("es-VE", {
      dateStyle: "medium",
      timeStyle: soloFecha ? undefined : "short",
    }).format(fecha);
  }

  function limpiarDetalle() {
    [datosProducto, datosProveedor, datosCatalogo, ofertasProducto].forEach(
      function (nodo) {
        if (nodo) nodo.replaceChildren();
      }
    );
  }

  function renderizarDetalle(datos) {
    var producto = datos.producto || {};
    if (tituloDetalle) tituloDetalle.textContent = producto.nombre || "Detalle del producto";
    agregarCampo(datosProducto, "Código", producto.codigo);
    agregarCampo(datosProducto, "Código interno", producto.codigo_interno);
    agregarCampo(datosProducto, "Marca", producto.marca);
    agregarCampo(datosProducto, "Categoría", producto.categoria);
    agregarCampo(datosProducto, "Descripción", producto.descripcion);
    agregarCampo(datosProducto, "Unidad", producto.unidad_medida);
    agregarCampo(datosProducto, "Presentación", producto.presentacion);
    agregarCampo(
      datosProducto,
      "Precio",
      formatearPrecio(producto.precio, producto.moneda)
    );
    agregarCampo(datosProducto, "IVA", Number(producto.iva) + " %");
    agregarCampo(datosProducto, "Descuento", Number(producto.descuentos) + " %");
    agregarCampo(datosProducto, "Existencias", producto.stock);
    agregarCampo(datosProducto, "Punto de reorden", producto.punto_reorden);
    agregarCampo(datosProducto, "Ubicación", producto.ubicacion);
    agregarCampo(
      datosProducto,
      "Última actualización",
      fechaLocal(producto.actualizado_en, false)
    );

    var proveedor = datos.proveedor;
    if (proveedor) {
      agregarCampo(datosProveedor, "Nombre", proveedor.nombre);
      agregarCampo(datosProveedor, "RIF", proveedor.rif);
      agregarCampo(datosProveedor, "Dirección", proveedor.direccion);
      agregarCampo(datosProveedor, "Teléfono", proveedor.telefono);
      agregarCampo(datosProveedor, "Correo", proveedor.correo);
      agregarCampo(datosProveedor, "Vendedor", proveedor.vendedor);
      agregarCampo(datosProveedor, "Teléfono del vendedor", proveedor.telefono_vendedor);
      agregarCampo(datosProveedor, "Correo del vendedor", proveedor.correo_vendedor);
      agregarCampo(datosProveedor, "Moneda", proveedor.moneda);
    } else {
      agregarCampo(datosProveedor, "Estado", "Sin proveedor registrado");
    }

    var catalogo = datos.catalogo;
    if (catalogo) {
      agregarCampo(datosCatalogo, "Archivo", catalogo.nombre);
      agregarCampo(datosCatalogo, "Formato", catalogo.tipo);
      agregarCampo(
        datosCatalogo,
        "Fecha de carga",
        fechaLocal(catalogo.fecha_de_subida, false)
      );
      agregarCampo(datosCatalogo, "Estado", catalogo.estado);
      agregarCampo(datosCatalogo, "Filas incorporadas", catalogo.filas_ok);
      agregarCampo(datosCatalogo, "Filas con error", catalogo.filas_error);
      agregarCampo(datosCatalogo, "Moneda", catalogo.moneda);
      agregarCampo(datosCatalogo, "Nota del proveedor", catalogo.nota_proveedor);
      agregarCampo(datosCatalogo, "Vendedor en la carga", catalogo.vendedor);
    } else {
      agregarCampo(datosCatalogo, "Estado", "No hay archivo de origen asociado");
    }

    var ofertas = datos.ofertas || [];
    if (ofertas.length === 0) {
      var sinOfertas = document.createElement("p");
      sinOfertas.textContent = "No hay otras ofertas registradas.";
      ofertasProducto.appendChild(sinOfertas);
    } else {
      ofertas.forEach(function (oferta) {
        var articulo = document.createElement("article");
        articulo.className = "buscador__oferta";
        var nombre = document.createElement("h4");
        nombre.textContent = oferta.proveedor || "Proveedor";
        articulo.appendChild(nombre);
        var lista = document.createElement("dl");
        lista.className = "buscador__detalle-lista";
        agregarCampo(lista, "Código proveedor", oferta.codigo_proveedor);
        agregarCampo(lista, "Precio", formatearPrecio(oferta.precio, oferta.moneda));
        agregarCampo(lista, "Descuento", oferta.descuento);
        agregarCampo(lista, "Disponible", oferta.disponible === null ? null : oferta.disponible ? "Sí" : "No");
        agregarCampo(
          lista,
          "Cantidad disponible",
          oferta.cantidad_disponible_proveedor
        );
        agregarCampo(lista, "Cantidad mínima", oferta.cantidad_minima);
        agregarCampo(lista, "Plazo de entrega (días)", oferta.plazo_entrega_dias);
        agregarCampo(lista, "Política de ventas", oferta.politica_ventas);
        agregarCampo(lista, "Cotización", fechaLocal(oferta.fecha_cotizacion, true));
        agregarCampo(lista, "Catálogo", oferta.catalogo);
        articulo.appendChild(lista);
        // ofertasProducto.appendChild(articulo);
      });
    }
  }

  function mostrarDetalle(idProducto, nombre) {
    if (!dialogoDetalle) return;
    var solicitud = ++solicitudDetalle;
    limpiarDetalle();
    if (tituloDetalle) tituloDetalle.textContent = nombre || "Detalle del producto";
    if (errorDetalle) {
      errorDetalle.textContent = "";
      errorDetalle.hidden = true;
    }
    if (contenidoDetalle) contenidoDetalle.hidden = true;
    mostrar(estadoDetalle);
    if (!dialogoDetalle.open) dialogoDetalle.showModal();
    Fipca.pedir("/api/v1/inventario/productos/" + encodeURIComponent(idProducto))
      .then(function (datos) {
        if (solicitud !== solicitudDetalle || !dialogoDetalle.open) return;
        ocultar(estadoDetalle);
        renderizarDetalle(datos);
        mostrar(contenidoDetalle);
      })
      .catch(function (falla) {
        if (solicitud !== solicitudDetalle || !dialogoDetalle.open) return;
        ocultar(estadoDetalle);
        if (errorDetalle) {
          errorDetalle.textContent = motivoDeFallo(falla);
          mostrar(errorDetalle);
        }
      });
  }

  function filaProducto(producto) {
    var fila = document.createElement("tr");
    fila.dataset.productoId = String(producto.id);
    fila.tabIndex = 0;
    fila.setAttribute(
      "aria-label",
      "Ver detalle de " + (producto.nombre || "producto")
    );

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
    // agregarDetalle(
    //   celdaProducto,
    //   "buscador__descripcion",
    //   producto.descripcion && producto.descripcion.length > 180
    //     ? producto.descripcion.slice(0, 179) + "…"
    //     : producto.descripcion
    // );

    agregarDetalle(celdaProducto, "buscador__descripcion", "");
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

  function tarjetaProducto(producto) {
    var nombre = producto.nombre || "Sin nombre registrado";
    var elemento = document.createElement("li");
    var boton = document.createElement("button");
    boton.className = "buscador__tarjeta";
    boton.type = "button";
    boton.dataset.productoId = String(producto.id);
    boton.setAttribute("aria-label", "Ver detalle de " + nombre);

    var cabecera = document.createElement("span");
    cabecera.className = "buscador__tarjeta-cabecera";
    var titulo = document.createElement("strong");
    titulo.className = "buscador__tarjeta-nombre";
    titulo.textContent = nombre;
    cabecera.appendChild(titulo);
    if (producto.codigo) {
      var codigo = document.createElement("code");
      codigo.className = "buscador__tarjeta-codigo";
      codigo.textContent = producto.codigo;
      cabecera.appendChild(codigo);
    }
    boton.appendChild(cabecera);

    var datos = document.createElement("span");
    datos.className = "buscador__tarjeta-datos";
    var precio = document.createElement("span");
    precio.className = "buscador__tarjeta-valor";
    var etiquetaPrecio = document.createElement("span");
    etiquetaPrecio.className = "buscador__tarjeta-etiqueta";
    etiquetaPrecio.textContent = "Precio";
    var valorPrecio = document.createElement("strong");
    valorPrecio.textContent = formatearPrecio(producto.precio, producto.moneda);
    precio.appendChild(etiquetaPrecio);
    precio.appendChild(valorPrecio);

    var stock = document.createElement("span");
    stock.className = "buscador__tarjeta-valor buscador__tarjeta-existencias";
    var etiquetaStock = document.createElement("span");
    etiquetaStock.className = "buscador__tarjeta-etiqueta";
    etiquetaStock.textContent = "Existencias";
    var existencias = Number(producto.stock);
    var valorStock = document.createElement("strong");
    valorStock.textContent = String(isNaN(existencias) ? 0 : existencias);
    valorStock.dataset.agotado =
      isNaN(existencias) || existencias <= 0 ? "1" : "";
    stock.appendChild(etiquetaStock);
    stock.appendChild(valorStock);
    datos.appendChild(precio);
    datos.appendChild(stock);
    boton.appendChild(datos);

    var proveedor = document.createElement("span");
    proveedor.className = "buscador__tarjeta-proveedor";
    var etiquetaProveedor = document.createElement("span");
    etiquetaProveedor.className = "buscador__tarjeta-etiqueta";
    etiquetaProveedor.textContent = "Proveedor";
    var nombreProveedor = document.createElement("span");
    nombreProveedor.textContent =
      producto.proveedor || "Sin proveedor registrado";
    proveedor.appendChild(etiquetaProveedor);
    proveedor.appendChild(nombreProveedor);
    boton.appendChild(proveedor);

    elemento.appendChild(boton);
    return elemento;
  }

  function renderizarProductos(lista) {
    if (filas) {
      filas.replaceChildren();
      lista.forEach(function (producto) {
        filas.appendChild(filaProducto(producto));
      });
    }
    if (tarjetas) {
      tarjetas.replaceChildren();
      lista.forEach(function (producto) {
        tarjetas.appendChild(tarjetaProducto(producto));
      });
    }
  }

  function pintarResultados(datos, milisegundos) {
    modoCatalogo = false;
    var lista = datos.productos || [];
    paginaActual = datos.pagina;
    totalActual = datos.total;
    renderizarProductos(lista);
    mostrar(contenedor);
    ocultar(vacio);
    mostrar(resumen);
    resumen.textContent =
      resumenDe(datos, milisegundos) +
      " Página " +
      datos.pagina +
      " de " +
      Math.max(1, Math.ceil(datos.total / datos.limite)) +
      ".";
    pintarPaginacion(datos);
  }

  function pintarPaginacion(datos) {
    var paginas = Math.max(1, Math.ceil(datos.total / datos.limite));
    var inicio = (datos.pagina - 1) * datos.limite + 1;
    var fin = inicio + (datos.productos || []).length - 1;
    mostrar(paginacion);
    if (estadoPaginacion) {
      estadoPaginacion.textContent =
        "Página " +
        datos.pagina +
        " de " +
        paginas +
        " · " +
        inicio +
        "–" +
        fin +
        " de " +
        datos.total;
    }
    if (anteriorCatalogo) anteriorCatalogo.disabled = datos.pagina <= 1;
    if (siguienteCatalogo) siguienteCatalogo.disabled = datos.pagina >= paginas;
  }

  function pintarCatalogo(datos, milisegundos) {
    var lista = datos.productos || [];
    paginaActual = datos.pagina;
    totalActual = datos.total;
    renderizarProductos(lista);
    mostrar(resumen);

    if (datos.total === 0) {
      ocultar(contenedor);
      fijarVacio(
        "Catálogo sin productos activos",
        "Todavía no hay productos activos para mostrar."
      );
      resumen.textContent = "Total del catálogo: 0 productos.";
      ocultar(paginacion);
      return;
    }

    mostrar(contenedor);
    ocultar(vacio);
    var inicio = (datos.pagina - 1) * datos.limite + 1;
    var fin = inicio + lista.length - 1;
    resumen.textContent =
      "Total del catálogo: " +
      datos.total +
      " productos. Mostrando " +
      inicio +
      "–" +
      fin +
      " en " +
      milisegundos +
      " ms.";
    pintarPaginacion(datos);
  }

  function pintarSinCoincidencias(datos, milisegundos, consulta) {
    ocultar(contenedor);
    ocultar(paginacion);
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

  function parametrosOrden() {
    if (!ordenarPor) return "";
    return (
      "&ordenar_por=" +
      encodeURIComponent(ordenarPor) +
      "&direccion=" +
      encodeURIComponent(direccionOrden)
    );
  }

  function buscar(consulta, pagina) {
    pagina = pagina || 1;
    modoCatalogo = false;
    ocultar(paginacion);
    if (botonCatalogo) botonCatalogo.disabled = false;
    var numero = ++peticion;
    mostrarError("");
    mostrar(cargando);
    var inicio = Date.now();

    Fipca.pedir(
      "/api/v1/inventario/busqueda?limite=" +
        LIMITE +
        "&pagina=" +
        encodeURIComponent(pagina) +
        "&consulta=" +
        encodeURIComponent(consulta) +
        parametrosOrden()
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

  function cargarPagina(pagina) {
    var numero = ++peticion;
    mostrarError("");
    mostrar(cargando);
    if (anteriorCatalogo) anteriorCatalogo.disabled = true;
    if (siguienteCatalogo) siguienteCatalogo.disabled = true;
    if (modoCatalogo && botonCatalogo) botonCatalogo.disabled = true;
    var inicio = Date.now();
    var consulta = entrada.value.trim();
    var ruta = modoCatalogo
      ? "/api/v1/inventario/catalogo?limite=" +
        LIMITE +
        "&pagina=" +
        encodeURIComponent(pagina) +
        parametrosOrden()
      : "/api/v1/inventario/busqueda?limite=" +
        LIMITE +
        "&pagina=" +
        encodeURIComponent(pagina) +
        "&consulta=" +
        encodeURIComponent(consulta) +
        parametrosOrden();

    Fipca.pedir(ruta)
      .then(function (datos) {
        if (numero !== peticion) return;
        ocultar(cargando);
        if (modoCatalogo) {
          if (botonCatalogo) botonCatalogo.disabled = false;
          pintarCatalogo(datos, Math.max(1, Date.now() - inicio));
        } else if (datos.productos.length) {
          pintarResultados(datos, Math.max(1, Date.now() - inicio));
        } else {
          pintarSinCoincidencias(datos, Math.max(1, Date.now() - inicio), consulta);
        }
      })
      .catch(function (falla) {
        if (numero !== peticion) return;
        ocultar(cargando);
        if (modoCatalogo && botonCatalogo) botonCatalogo.disabled = false;
        if (anteriorCatalogo) anteriorCatalogo.disabled = paginaActual <= 1;
        if (siguienteCatalogo) {
          siguienteCatalogo.disabled =
            paginaActual >= Math.ceil(totalActual / LIMITE);
        }
        mostrarError(motivoDeFallo(falla));
      });
  }

  function actualizarOrdenVisual() {
    document.querySelectorAll("[data-ordenar-por]").forEach(function (boton) {
      var columna = boton.getAttribute("data-ordenar-por");
      var encabezado = boton.closest("th");
      var seleccionado = columna === ordenarPor;
      if (encabezado) {
        encabezado.setAttribute(
          "aria-sort",
          seleccionado
            ? direccionOrden === "asc"
              ? "ascending"
              : "descending"
            : "none"
        );
      }
      boton.setAttribute(
        "aria-label",
        "Ordenar por " +
          boton.getAttribute("data-etiqueta-orden") +
          " " +
          (seleccionado && direccionOrden === "asc" ? "descendente" : "ascendente")
      );
    });
    if (ordenMovil) {
      ordenMovil.value = ordenarPor
        ? ordenarPor + ":" + direccionOrden
        : "";
    }
  }

  function actualizarResultadosOrdenados() {
    actualizarOrdenVisual();
    if (modoCatalogo) {
      cargarPagina(1);
    } else if (entrada.value.trim()) {
      buscar(entrada.value.trim(), 1);
    }
  }

  function ordenarResultados(columna) {
    cancelarPendiente();
    if (ordenarPor === columna) {
      direccionOrden = direccionOrden === "asc" ? "desc" : "asc";
    } else {
      ordenarPor = columna;
      direccionOrden = "asc";
    }
    actualizarResultadosOrdenados();
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
    peticion += 1;
    modoCatalogo = false;
    ocultar(paginacion);
    if (botonCatalogo) botonCatalogo.disabled = false;
    if (consulta.length < MINIMO_BUSQUEDA) {
      mostrarReposo();
      return;
    }
    programar(consulta);
  });

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    var consulta = entrada.value.trim();
    if (consulta.length < MINIMO_BUSQUEDA) {
      mostrarError("Escriba al menos " + MINIMO_BUSQUEDA + " carácter para buscar.");
      entrada.focus();
      return;
    }
    cancelarPendiente();
    buscar(consulta);
  });

  if (botonCatalogo) {
    botonCatalogo.addEventListener("click", function () {
      cancelarPendiente();
      entrada.value = "";
      modoCatalogo = true;
      cargarPagina(1);
    });
  }

  if (anteriorCatalogo) {
    anteriorCatalogo.addEventListener("click", function () {
      if (paginaActual > 1) {
        cargarPagina(paginaActual - 1);
      }
    });
  }

  if (siguienteCatalogo) {
    siguienteCatalogo.addEventListener("click", function () {
      if (paginaActual < Math.ceil(totalActual / LIMITE)) {
        cargarPagina(paginaActual + 1);
      }
    });
  }

  if (limiteResultados) {
    limiteResultados.addEventListener("change", function () {
      LIMITE = Number(limiteResultados.value);
      cancelarPendiente();
      if (modoCatalogo) {
        cargarPagina(1);
      } else if (entrada.value.trim()) {
        buscar(entrada.value.trim(), 1);
      }
    });
  }

  document.querySelectorAll("[data-ordenar-por]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      ordenarResultados(boton.getAttribute("data-ordenar-por"));
    });
  });
  if (ordenMovil) {
    ordenMovil.addEventListener("change", function () {
      var valor = ordenMovil.value.split(":");
      cancelarPendiente();
      ordenarPor = valor.length === 2 ? valor[0] : null;
      direccionOrden = valor.length === 2 ? valor[1] : "asc";
      actualizarResultadosOrdenados();
    });
  }
  actualizarOrdenVisual();

  document.querySelectorAll("[data-buscar]").forEach(function (atajo) {
    atajo.addEventListener("click", function () {
      entrada.value = atajo.getAttribute("data-buscar") || "";
      cancelarPendiente();
      modoCatalogo = false;
      ocultar(paginacion);
      if (botonCatalogo) botonCatalogo.disabled = false;
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


  if (filas) {
    filas.addEventListener("click", function (evento) {
      var fila = evento.target.closest("tr[data-producto-id]");
      if (fila && filas.contains(fila)) {
        mostrarDetalle(fila.dataset.productoId, fila.getAttribute("aria-label"));
      }
    });
    filas.addEventListener("keydown", function (evento) {
      if (
        (evento.key === "Enter" || evento.key === " ") &&
        evento.target.matches("tr[data-producto-id]")
      ) {
        evento.preventDefault();
        mostrarDetalle(
          evento.target.dataset.productoId,
          evento.target.getAttribute("aria-label")
        );
      }
    });
  }
  if (tarjetas) {
    tarjetas.addEventListener("click", function (evento) {
      var boton = evento.target.closest("button[data-producto-id]");
      if (boton && tarjetas.contains(boton)) {
        mostrarDetalle(boton.dataset.productoId, boton.getAttribute("aria-label"));
      }
    });
  }
  if (cerrarDetalle && dialogoDetalle) {
    cerrarDetalle.addEventListener("click", function () {
      dialogoDetalle.close();
    });
    dialogoDetalle.addEventListener("close", function () {
      solicitudDetalle += 1;
    });
  }

})();

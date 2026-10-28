/* Estado y limites visibles unicamente para administradores. */
(function () {
  "use strict";

  var contenedor = document.getElementById("estado-tecnico");
  if (!contenedor) return;
  var aviso = document.getElementById("aviso-configuracion");

  function crearDato(etiqueta, valor, estado) {
    var fila = document.createElement("div");
    var nombre = document.createElement("dt");
    nombre.textContent = etiqueta;
    var dato = document.createElement("dd");
    dato.textContent = valor;
    if (estado) {
      dato.className = "configuracion-estado configuracion-estado--" + estado;
    }
    fila.append(nombre, dato);
    return fila;
  }

  async function cargar() {
    try {
      var datos = await window.Fipca.pedir("/api/v1/auth/configuracion/admin");
      var fragmento = document.createDocumentFragment();
      var estado = document.createElement("dl");
      estado.className = "configuracion-datos configuracion-datos--tecnicos";
      Object.keys(datos.bases).forEach(function (base) {
        var operativa = datos.bases[base] === "operativa";
        estado.appendChild(crearDato(
          "Base de datos · " + base,
          datos.bases[base],
          operativa ? "ok" : "fallo"
        ));
      });

      var ingesta = datos.ingesta;
      estado.appendChild(crearDato("Formatos de catálogo", ingesta.formatos.join(", ")));
      estado.appendChild(crearDato("Tamaño por archivo", ingesta.max_archivo_mb + " MB"));
      estado.appendChild(crearDato("Archivos por lote", String(ingesta.max_archivos)));
      estado.appendChild(crearDato("Filas máximas por archivo", ingesta.max_filas_archivo.toLocaleString("es-VE")));
      estado.appendChild(crearDato("Páginas máximas por PDF", String(ingesta.max_paginas_pdf)));
      estado.appendChild(crearDato("Imagen de perfil", "JPEG, PNG o WebP · " + datos.imagen_perfil_max_mb + " MB"));
      fragmento.appendChild(estado);
      contenedor.replaceChildren(fragmento);
    } catch (error) {
      contenedor.replaceChildren();
      window.Fipca.aviso(aviso, error.message, "error");
    }
  }

  cargar();
})();

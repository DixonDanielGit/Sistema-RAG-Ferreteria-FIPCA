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

(function () {
  "use strict";

  var tabla = document.getElementById("filas-roles");
  var formulario = document.getElementById("form-rol");
  var opciones = document.getElementById("opciones-permisos");
  var aviso = document.getElementById("aviso-roles");
  if (!tabla || !formulario || !opciones) return;

  var roles = [];
  var permisos = [];
  var botonGuardar = document.getElementById("guardar-rol");
  var botonCancelar = document.getElementById("cancelar-edicion-rol");
  var titulo = document.getElementById("form-rol-titulo");

  function celda(texto, clase) {
    var elemento = document.createElement("td");
    if (clase) elemento.className = clase;
    elemento.textContent = texto;
    return elemento;
  }

  function mostrarPermisos(claves) {
    return claves
      .map(function (clave) {
        var permiso = permisos.find(function (item) {
          return item.clave === clave;
        });
        return permiso ? permiso.nombre : clave;
      })
      .join(", ") || "Sin capacidades asignadas";
  }

  function crearAccion(texto, accion, id, usuario) {
    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "btn-fipca btn-fipca--fantasma";
    boton.dataset.accionRol = accion;
    boton.dataset.idRol = String(id);
    boton.setAttribute("aria-label", texto + " rol " + usuario);
    boton.textContent = texto;
    return boton;
  }

  function dibujarRoles() {
    var fragmento = document.createDocumentFragment();
    roles.forEach(function (rol) {
      var fila = document.createElement("tr");
      var nombre = document.createElement("strong");
      nombre.textContent = rol.nombre === "admin" ? "Administrador" : rol.nombre;
      var descripcion = document.createElement("span");
      descripcion.className = "roles-tabla__descripcion";
      descripcion.textContent = rol.descripcion || "Sin descripción";
      var celdaNombre = document.createElement("td");
      celdaNombre.append(nombre, descripcion);

      var celdaPermisos = document.createElement("td");
      var resumen = document.createElement("span");
      resumen.className = "roles-tabla__permisos";
      resumen.textContent = mostrarPermisos(rol.permisos);
      celdaPermisos.appendChild(resumen);

      var celdaCuentas = celda(
        String(rol.usuarios_asignados) +
          (rol.usuarios_asignados === 1 ? " cuenta" : " cuentas")
      );
      var acciones = document.createElement("td");
      if (rol.protegido) {
        var proteccion = document.createElement("span");
        proteccion.className = "roles-tabla__proteccion";
        proteccion.textContent = "Protegido";
        acciones.appendChild(proteccion);
      } else {
        var grupo = document.createElement("div");
        grupo.className = "roles-tabla__acciones";
        grupo.append(
          crearAccion("Editar", "editar", rol.id_rol, rol.nombre),
          crearAccion("Eliminar", "eliminar", rol.id_rol, rol.nombre)
        );
        acciones.appendChild(grupo);
      }

      fila.append(celdaNombre, celdaPermisos, celdaCuentas, acciones);
      fragmento.appendChild(fila);
    });

    if (!roles.length) {
      var vacio = document.createElement("tr");
      vacio.appendChild(celda("Todavía no hay roles configurados."));
      vacio.firstElementChild.colSpan = 4;
      fragmento.appendChild(vacio);
    }
    tabla.replaceChildren(fragmento);
  }

  function dibujarOpcionesPermiso() {
    var fragmento = document.createDocumentFragment();
    permisos.forEach(function (permiso) {
      var etiqueta = document.createElement("label");
      etiqueta.className = "roles-permisos__opcion";
      var entrada = document.createElement("input");
      entrada.type = "checkbox";
      entrada.name = "permisos";
      entrada.value = permiso.clave;

      var texto = document.createElement("span");
      var nombre = document.createElement("strong");
      nombre.textContent = permiso.nombre;
      var descripcion = document.createElement("small");
      descripcion.textContent = permiso.descripcion;
      texto.append(nombre, descripcion);
      etiqueta.append(entrada, texto);
      fragmento.appendChild(etiqueta);
    });
    opciones.replaceChildren(fragmento);
  }

  function limpiarFormulario() {
    formulario.reset();
    formulario.elements.id_rol.value = "";
    formulario.elements.nombre.disabled = false;
    titulo.textContent = "Crear rol";
    botonGuardar.textContent = "Crear rol";
    botonCancelar.hidden = true;
  }

  function editarRol(rol) {
    formulario.elements.id_rol.value = String(rol.id_rol);
    formulario.elements.nombre.value = rol.nombre;
    formulario.elements.descripcion.value = rol.descripcion || "";
    formulario.elements.nombre.disabled = false;
    formulario.querySelectorAll('input[name="permisos"]').forEach(function (entrada) {
      entrada.checked = rol.permisos.indexOf(entrada.value) !== -1;
    });
    titulo.textContent = "Editar rol";
    botonGuardar.textContent = "Guardar cambios";
    botonCancelar.hidden = false;
    formulario.elements.nombre.focus();
  }

  async function cargarRoles() {
    try {
      var resultado = await Promise.all([
        window.Fipca.pedir("/api/v1/auth/roles"),
        window.Fipca.pedir("/api/v1/auth/roles/permisos"),
      ]);
      roles = resultado[0];
      permisos = resultado[1];
      dibujarRoles();
      dibujarOpcionesPermiso();
    } catch (error) {
      await window.Fipca.aviso(aviso, error.message, "error");
      tabla.replaceChildren();
      var fallo = document.createElement("tr");
      var mensaje = celda("No se pudieron cargar los roles y sus capacidades.");
      mensaje.colSpan = 4;
      fallo.appendChild(mensaje);
      tabla.appendChild(fallo);
      opciones.textContent = "No se pudieron cargar las capacidades.";
    }
  }

  formulario.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    if (!formulario.reportValidity()) return;

    var id = formulario.elements.id_rol.value;
    var datos = {
      nombre: formulario.elements.nombre.value.trim(),
      descripcion: formulario.elements.descripcion.value.trim(),
      permisos: Array.prototype.map.call(
        formulario.querySelectorAll('input[name="permisos"]:checked'),
        function (entrada) {
          return entrada.value;
        }
      ),
    };
    botonGuardar.disabled = true;
    try {
      await window.Fipca.pedir(
        id
          ? "/api/v1/auth/roles/" + encodeURIComponent(id)
          : "/api/v1/auth/roles",
        { metodo: id ? "PUT" : "POST", cuerpo: datos }
      );
      limpiarFormulario();
      await cargarRoles();
      await window.Fipca.aviso(
        null,
        id ? "Los cambios del rol se guardaron." : "El rol se creó correctamente.",
        "exito"
      );
    } catch (error) {
      await window.Fipca.aviso(aviso, error.message, "error");
    } finally {
      botonGuardar.disabled = false;
    }
  });

  botonCancelar.addEventListener("click", limpiarFormulario);

  tabla.addEventListener("click", async function (evento) {
    var boton = evento.target.closest("button[data-accion-rol]");
    if (!boton) return;
    var rol = roles.find(function (item) {
      return String(item.id_rol) === boton.dataset.idRol;
    });
    if (!rol) return;

    if (boton.dataset.accionRol === "editar") {
      editarRol(rol);
      return;
    }

    var confirmacion = await window.Swal.fire({
      icon: "warning",
      title: "¿Eliminar este rol?",
      text: rol.usuarios_asignados
        ? "No se puede eliminar mientras tenga cuentas asignadas."
        : "Las cuentas no se eliminan; solo se quitará la configuración del rol.",
      showCancelButton: true,
      confirmButtonText: "Eliminar rol",
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

    boton.disabled = true;
    try {
      await window.Fipca.pedir("/api/v1/auth/roles/" + encodeURIComponent(rol.id_rol), {
        metodo: "DELETE",
      });
      await cargarRoles();
      await window.Fipca.aviso(null, "El rol se eliminó.", "exito");
    } catch (error) {
      await window.Fipca.aviso(aviso, error.message, "error");
    } finally {
      boton.disabled = false;
    }
  });

  cargarRoles();
})();

/* Gestion administrativa de perfiles y capacidades. */
(function () {
  "use strict";

  var lista = document.getElementById("lista-roles");
  var aviso = document.getElementById("aviso-roles");
  var formulario = document.getElementById("form-rol");
  var opciones = document.getElementById("opciones-permisos");
  var busqueda = document.getElementById("buscar-roles");
  var resumen = document.getElementById("resumen-roles");
  var paginacion = document.getElementById("paginacion-roles");
  var paginas = document.getElementById("paginas-roles");
  var plantillaIlustracion = document.getElementById("plantilla-ilustracion-rol");
  if (!lista || !formulario || !opciones) return;

  var ROLES_POR_PAGINA = 4;
  var roles = [];
  var permisos = [];
  var paginaActual = 1;
  var campoId = formulario.elements.id_rol;
  var campoNombre = formulario.elements.nombre;
  var campoDescripcion = formulario.elements.descripcion;
  var botonGuardar = document.getElementById("guardar-rol");
  var etiquetaGuardar = document.getElementById("guardar-rol-etiqueta");
  var modalFormulario = window.bootstrap.Modal.getOrCreateInstance(
    document.getElementById("modal-rol")
  );
  var modalDetalle = window.bootstrap.Modal.getOrCreateInstance(
    document.getElementById("modal-detalle-rol")
  );
  var guardando = false;

  function nombreVisible(nombre) {
    return nombre === "admin" ? "Administrador" : nombre;
  }

  function normalizarBusqueda(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("es");
  }

  function mostrarError(error) {
    window.Fipca.aviso(aviso, error.message, "error");
  }

  function crearElemento(etiqueta, clase, texto) {
    var elemento = document.createElement(etiqueta);
    if (clase) elemento.className = clase;
    if (texto !== undefined) elemento.textContent = texto;
    return elemento;
  }

  function crearIcono(accion) {
    var icono = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icono.setAttribute("viewBox", "0 0 24 24");
    icono.setAttribute("fill", "none");
    icono.setAttribute("stroke", "currentColor");
    icono.setAttribute("stroke-width", "1.8");
    icono.setAttribute("stroke-linecap", "round");
    icono.setAttribute("stroke-linejoin", "round");
    icono.setAttribute("aria-hidden", "true");
    icono.setAttribute("focusable", "false");

    var trazos = {
      editar: [
        ["path", "M12 20h9"],
        ["path", "M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"],
      ],
      eliminar: [
        ["path", "M3 6h18"],
        ["path", "M8 6V4h8v2"],
        ["path", "m19 6-1 14H6L5 6"],
        ["path", "M10 11v5m4-5v5"],
      ],
      detalle: [
        ["path", "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"],
        ["circle", null],
      ],
    };

    trazos[accion].forEach(function (trazo) {
      var elemento = document.createElementNS(
        "http://www.w3.org/2000/svg",
        trazo[0]
      );
      if (trazo[1]) {
        elemento.setAttribute("d", trazo[1]);
      } else {
        elemento.setAttribute("cx", "12");
        elemento.setAttribute("cy", "12");
        elemento.setAttribute("r", "3");
      }
      icono.appendChild(elemento);
    });
    return icono;
  }

  function crearBoton(etiqueta, accion, rol, deshabilitado, motivo) {
    var boton = crearElemento("button", "btn-fipca btn-fipca--fantasma");
    boton.type = "button";
    boton.dataset.accionRol = accion;
    boton.dataset.idRol = String(rol.id_rol);
    var nombreAccion = etiqueta + " " + nombreVisible(rol.nombre);
    boton.setAttribute("aria-label", nombreAccion);
    boton.title = nombreAccion;
    boton.append(crearIcono(accion));
    if (deshabilitado) {
      boton.disabled = true;
      boton.title += ". " + motivo;
    }
    return boton;
  }

  function crearTarjeta(rol) {
    var tarjeta = crearElemento("article", "roles-tarjeta");
    var ilustracion = plantillaIlustracion.content.cloneNode(true);

    var contenido = crearElemento("div", "roles-tarjeta__contenido");
    contenido.appendChild(crearElemento("h3", "", nombreVisible(rol.nombre)));
    contenido.appendChild(
      crearElemento("p", "", rol.descripcion || "Sin descripción")
    );
    var asignacion =
      rol.usuarios_asignados +
      (rol.usuarios_asignados === 1 ? " cuenta asignada" : " cuentas asignadas");
    var capacidad =
      rol.permisos.length +
      (rol.permisos.length === 1 ? " capacidad" : " capacidades");
    var estado = crearElemento(
      "span",
      "roles-tarjeta__estado" + (rol.protegido ? " roles-tarjeta__estado--protegido" : ""),
      rol.protegido ? "Protegido · " + asignacion : asignacion + " · " + capacidad
    );
    contenido.appendChild(estado);

    var acciones = crearElemento("div", "roles-tarjeta__acciones");
    var motivo = "El rol Administrador está protegido por el sistema.";
    acciones.append(
      crearBoton("Editar", "editar", rol, rol.protegido, motivo),
      crearBoton("Eliminar", "eliminar", rol, rol.protegido, motivo),
      crearBoton("Más información", "detalle", rol, false, "")
    );
    tarjeta.append(ilustracion, contenido, acciones);
    return tarjeta;
  }

  function rolesFiltrados() {
    var consulta = normalizarBusqueda(busqueda.value.trim());
    if (!consulta) return roles;
    return roles.filter(function (rol) {
      var datos = [rol.nombre, nombreVisible(rol.nombre), rol.descripcion];
      rol.permisos.forEach(function (clave) {
        var permiso = permisos.find(function (item) {
          return item.clave === clave;
        });
        datos.push(clave);
        if (permiso) datos.push(permiso.nombre, permiso.descripcion);
      });
      return normalizarBusqueda(datos.join(" ")).includes(consulta);
    });
  }

  function dibujarPaginacion(totalPaginas) {
    if (!paginacion || !paginas) return;
    paginacion.hidden = totalPaginas <= 1;
    paginas.replaceChildren();
    if (totalPaginas <= 1) return;

    var anterior = paginacion.querySelector('[data-pagina-rol="anterior"]');
    var siguiente = paginacion.querySelector('[data-pagina-rol="siguiente"]');
    anterior.disabled = paginaActual === 1;
    siguiente.disabled = paginaActual === totalPaginas;

    for (var numero = 1; numero <= totalPaginas; numero += 1) {
      var boton = crearElemento("button", "btn-fipca btn-fipca--fantasma", String(numero));
      boton.type = "button";
      boton.dataset.paginaRol = String(numero);
      boton.setAttribute("aria-label", "Página " + numero);
      if (numero === paginaActual) {
        boton.setAttribute("aria-current", "page");
      }
      paginas.appendChild(boton);
    }
  }

  function dibujarRoles() {
    var fragmento = document.createDocumentFragment();
    var filtrados = rolesFiltrados();
    var totalPaginas = Math.ceil(filtrados.length / ROLES_POR_PAGINA);
    paginaActual = Math.min(paginaActual, Math.max(totalPaginas, 1));

    if (roles.length === 0) {
      fragmento.appendChild(
        crearElemento("p", "roles-estado", "Todavía no hay roles configurados.")
      );
      resumen.textContent = "";
    } else if (filtrados.length === 0) {
      fragmento.appendChild(
        crearElemento(
          "p",
          "roles-estado",
          "No se encontraron roles que coincidan con su búsqueda."
        )
      );
      resumen.textContent = "0 roles encontrados.";
    } else {
      var inicio = (paginaActual - 1) * ROLES_POR_PAGINA;
      var visibles = filtrados.slice(inicio, inicio + ROLES_POR_PAGINA);
      visibles.forEach(function (rol) {
        fragmento.appendChild(crearTarjeta(rol));
      });
      resumen.textContent =
        "Mostrando " +
        (inicio + 1) +
        "–" +
        (inicio + visibles.length) +
        " de " +
        filtrados.length +
        (filtrados.length === 1 ? " rol." : " roles.");
    }
    lista.replaceChildren(fragmento);
    lista.setAttribute("aria-busy", "false");
    dibujarPaginacion(totalPaginas);
  }

  async function cargarRoles() {
    lista.setAttribute("aria-busy", "true");
    try {
      var datos = await window.Fipca.pedir("/api/v1/auth/roles");
      roles = datos;
      dibujarRoles();
      await window.Fipca.aviso(aviso, "");
    } catch (error) {
      lista.replaceChildren(
        crearElemento("p", "roles-estado", "No se pudieron cargar los roles.")
      );
      lista.setAttribute("aria-busy", "false");
      mostrarError(error);
    }
  }

  function dibujarPermisos(seleccionados) {
    var fragmento = document.createDocumentFragment();
    if (permisos.length === 0) {
      fragmento.appendChild(
        crearElemento("p", "", "No hay capacidades disponibles para asignar.")
      );
      opciones.replaceChildren(fragmento);
      return;
    }

    permisos.forEach(function (permiso) {
      var etiqueta = crearElemento("label", "roles-permisos__opcion");
      var entrada = crearElemento("input");
      entrada.type = "checkbox";
      entrada.name = "permisos";
      entrada.value = permiso.clave;
      entrada.checked = seleccionados.indexOf(permiso.clave) !== -1;
      var texto = crearElemento("span");
      texto.appendChild(crearElemento("strong", "", permiso.nombre));
      texto.appendChild(crearElemento("small", "", permiso.descripcion));
      etiqueta.append(entrada, texto);
      fragmento.appendChild(etiqueta);
    });
    opciones.replaceChildren(fragmento);
  }

  function prepararModal(rol) {
    formulario.reset();
    campoId.value = rol ? String(rol.id_rol) : "";
    campoNombre.value = rol ? rol.nombre : "";
    campoNombre.readOnly = Boolean(rol && rol.protegido);
    campoDescripcion.value = rol ? rol.descripcion || "" : "";
    dibujarPermisos(rol ? rol.permisos : []);
    document.getElementById("form-rol-titulo").textContent = rol
      ? "Editar rol"
      : "Crear rol";
    etiquetaGuardar.textContent = rol ? "Guardar cambios" : "Crear rol";
    window.Fipca.aviso(aviso, "");
    modalFormulario.show();
    window.setTimeout(function () {
      campoNombre.focus();
    }, 150);
  }

  function mostrarDetalle(rol) {
    document.getElementById("detalle-rol-titulo").textContent =
      nombreVisible(rol.nombre);
    document.getElementById("detalle-rol-descripcion").textContent =
      rol.descripcion || "Este rol no tiene descripción.";
    var numeroCuentas = rol.usuarios_asignados;


    var listaPermisos = document.getElementById("detalle-rol-permisos");
    var fragmento = document.createDocumentFragment();
    rol.permisos.forEach(function (clave) {
      var permiso = permisos.find(function (item) {
        return item.clave === clave;
      });
      var elemento = crearElemento("li");
      elemento.appendChild(
        crearElemento("strong", "", permiso ? permiso.nombre : clave)
      );
      if (permiso) {
        elemento.appendChild(
          crearElemento("small", "", permiso.descripcion)
        );
      }
      fragmento.appendChild(elemento);
    });
    if (rol.permisos.length === 0) {
      fragmento.appendChild(
        crearElemento("li", "", "Este rol no tiene capacidades asignadas.")
      );
    }
    listaPermisos.replaceChildren(fragmento);
    modalDetalle.show();
  }

  async function eliminarRol(rol) {
    var confirmacion = await window.Swal.fire({
      icon: "warning",
      title: "¿Eliminar este rol?",
      text: "La acción es permanente y no se puede deshacer.",
      showCancelButton: true,
      confirmButtonText: "Eliminar rol",
      cancelButtonText: "Cancelar",
      buttonsStyling: false,
      customClass: {
        popup: "fipca-alerta",
        confirmButton: "btn-fipca",
        cancelButton: "btn-fipca btn-fipca--fantasma",
      },
    });
    if (!confirmacion.isConfirmed) return;

    try {
      await window.Fipca.pedir("/api/v1/auth/roles/" + rol.id_rol, {
        metodo: "DELETE",
      });
      await window.Fipca.aviso(null, "El rol se eliminó correctamente.", "exito");
      await cargarRoles();
    } catch (error) {
      mostrarError(error);
    }
  }

  async function cargarDatosIniciales() {
    try {
      var resultados = await Promise.all([
        window.Fipca.pedir("/api/v1/auth/roles"),
        window.Fipca.pedir("/api/v1/auth/roles/permisos"),
      ]);
      roles = resultados[0];
      permisos = resultados[1];
      dibujarRoles();
    } catch (error) {
      lista.replaceChildren(
        crearElemento("p", "roles-estado", "No se pudieron cargar los roles.")
      );
      lista.setAttribute("aria-busy", "false");
      mostrarError(error);
    }
  }

  document.getElementById("abrir-modal-rol").addEventListener("click", function () {
    prepararModal(null);
  });

  lista.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-accion-rol]");
    if (!boton || boton.disabled) return;
    var rol = roles.find(function (item) {
      return String(item.id_rol) === boton.dataset.idRol;
    });
    if (!rol) return;

    if (boton.dataset.accionRol === "editar") {
      prepararModal(rol);
    } else if (boton.dataset.accionRol === "eliminar") {
      eliminarRol(rol);
    } else if (boton.dataset.accionRol === "detalle") {
      mostrarDetalle(rol);
    }
  });

  if (busqueda) {
    busqueda.addEventListener("input", function () {
      paginaActual = 1;
      dibujarRoles();
    });
  }

  if (paginacion) {
    paginacion.addEventListener("click", function (evento) {
      var boton = evento.target.closest("[data-pagina-rol]");
      if (!boton || boton.disabled) return;

      if (boton.dataset.paginaRol === "anterior") {
        paginaActual -= 1;
      } else if (boton.dataset.paginaRol === "siguiente") {
        paginaActual += 1;
      } else {
        paginaActual = Number(boton.dataset.paginaRol);
      }
      dibujarRoles();
    });
  }

  formulario.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    if (guardando) return;
    if (!formulario.reportValidity()) return;

    guardando = true;
    botonGuardar.disabled = true;
    botonGuardar.querySelector(".spinner-border").hidden = false;
    var id = campoId.value;
    var datos = {
      nombre: campoNombre.value.trim(),
      descripcion: campoDescripcion.value.trim(),
      permisos: Array.from(
        formulario.querySelectorAll('input[name="permisos"]:checked')
      ).map(function (entrada) {
        return entrada.value;
      }),
    };

    try {
      await window.Fipca.pedir(
        id ? "/api/v1/auth/roles/" + id : "/api/v1/auth/roles",
        { metodo: id ? "PUT" : "POST", cuerpo: datos }
      );
      modalFormulario.hide();
      await window.Fipca.aviso(
        null,
        id ? "Los cambios del rol se guardaron." : "El rol se creó correctamente.",
        "exito"
      );
      await cargarRoles();
    } catch (error) {
      mostrarError(error);
    } finally {
      guardando = false;
      botonGuardar.disabled = false;
      botonGuardar.querySelector(".spinner-border").hidden = true;
    }
  });

  cargarDatosIniciales();
})();

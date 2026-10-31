# Guía de Implementación de Formularios con Validación Dinámica y Diseño Compacto

Este documento establece el estándar técnico y visual para la creación de nuevos formularios y modales en el sistema **FERRE-INVERSIONES PEREZ C.A. (FIPCA)**, utilizando el módulo de validaciones en vivo (`expresionesRegulares.js`) y el sistema de estilos de `estilos.css`.

---

## 1. Arquitectura del Sistema de Validación

El sistema consta de tres capas coordinadas:

1. **Estructura HTML (`templates/`)**: Contenedores semánticos (`.campo-custom`, `.campo-input-contenedor`) que integran el control, los iconos de estado (`.check`, `.error`) y el mensaje de error (`.p-error-validaciones`).
2. **Módulo JS (`app/static/js/expresionesRegulares.js`)**: Valida en tiempo real (`input`, `keyup`, `blur`, `change`), aplica clases dinámicas (`.valido`, `.invalido`) y gestiona el estado del formulario.
3. **Capa CSS (`app/static/css/estilos.css`)**: Regula el espaciado compacto, posicionamiento absoluto de iconos a la derecha, colores de borde/fondo de validación y soporte de tema claro/oscuro.

---

## 2. Estructura HTML Estándar para Cada Campo

Cada campo interactivo dentro de un formulario debe seguir obligatoriamente esta jerarquía:

```html
<div class="cuenta-campo campo-custom">
  <label for="campo-ejemplo" class="form-label">Nombre del Campo</label>
  <div class="campo-input-contenedor">
    <input
      type="text"
      class="form-control input-custom input-validar"
      id="campo-ejemplo"
      name="nombre_clave"
      placeholder="Texto de ayuda"
      autocomplete="off"
      required
    />
    <span class="icono-der" aria-hidden="true">
      <!-- Icono de Éxito (Check) -->
      <svg class="check d-none" width="18" height="18" fill="currentColor" viewBox="0 0 16 16">
        <path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425a.247.247 0 0 1 .02-.022Z" />
      </svg>
      <!-- Icono de Error (X) -->
      <svg class="error d-none" width="18" height="18" fill="currentColor" viewBox="0 0 16 16">
        <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z" />
      </svg>
    </span>
  </div>
  <p class="p-error-validaciones d-none"></p>
</div>
```

### Reglas Clave del HTML:
- El atributo `name` del `<input>` o `<select>` debe coincidir exactamente con una clave definida en el objeto `expresiones` de `expresionesRegulares.js` (ej: `cedula`, `nombre`, `apellido`, `usuario`, `correo`, `password`, `passwordConf`, `rol`).
- La clase `.input-validar` es la que detecta `inicializarValidacionFormulario()`.
- La clase `.campo-input-contenedor` asegura que `.icono-der` se posicione de forma flotante dentro del input sin alterar la altura ni generar saltos de línea.
- El párrafo `<p class="p-error-validaciones d-none"></p>` permanece oculto por defecto y no añade espacio vertical no deseado hasta que se activa un error.

---

## 3. Espaciado Compacto en Modales

Para evitar espacios excesivos entre filas de campos en un modal:
1. En el `<div class="modal-body">`, añade la clase `.formulario-compacto`:
   ```html
   <div class="modal-body formulario-compacto">
   ```
2. Esto activa las reglas CSS optimizadas:
   - `display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));`
   - `align-items: start;` (mantiene todos los campos alineados a la parte superior de cada fila, evitando que los errores desplacen los campos vecinos hacia abajo).
   - `gap: var(--esp-2) var(--esp-4);` (8px de separación vertical y 24px horizontal).
   - `margin-bottom: 0;` en los `.cuenta-campo` internos.

En pantallas de **470 px o menos**, todos los campos deben presentarse en una
sola columna. `estilos.css` aplica este estándar a `.cuenta-formulario`,
`.cuenta-modal .modal-body`, `.formulario-compacto` y `.form-grid`; los
formularios de una sola columna conservan su distribución. Mantenga este
breakpoint al añadir nuevas rejillas o filas de campos.

---

## 4. Registro y Configuración de Nuevas Expresiones Regulares

Para añadir nuevas reglas de validación a otros formularios (por ejemplo, productos, categorías, proveedores):

Abre `app/static/js/expresionesRegulares.js` y añade la regla dentro del objeto `expresiones`:

```javascript
export const expresiones = {
  // Ejemplo: nuevo campo "rif"
  rif: {
    expresion: /^[JVEGjveg]-?\d{8,9}$/,
    mensajeError: "Formato de RIF inválido (ej: J-123456789).",
  },
  // ... campos existentes ...
};
```

### Campos con Comportamientos Especiales:
- **`passwordConf`**: Valida automáticamente que su valor sea idéntico al campo con `name="password"`. Además, cuando se edita el campo `password`, el validador vuelve a verificar en tiempo real `passwordConf`.
- Si `passwordConf` es opcional y está vacío (por ejemplo, al editar una cuenta sin cambiar su contraseña), no bloquea el envío. Cuando es obligatorio, conserva su validación de coincidencia y expresión regular.
- **`<select>`**: Valida que la opción seleccionada no sea cadena vacía ni `"selection"` y cumpla la expresión regular asignada.
- El formulario de perfil valida `nombre`, `apellido`, `cedula`, `usuario` y `correo` con las reglas existentes antes de enviar el `PUT`. `novalidate` permite que los errores se muestren junto a cada campo mediante el validador común; no sustituye la validación del servidor.

### Validaciones autoritativas en el backend

La validación del navegador es una ayuda de experiencia de usuario; las solicitudes también deben validarse en el servidor. Para cuentas y autenticación, las responsabilidades se ubican así:

- `app/schemas/usuario_schema.py`: formato y normalización de campos de entrada (cédula, nombre, usuario, correo, rol y token), límites y rechazo de campos extra. Los validadores compartidos se reutilizan en registro, perfil, administración y recuperación.
- `app/main.py`: convierte los errores de validación de FastAPI a una respuesta JSON consistente (`ok`, `mensaje`, `detail` y `errores` por campo), sin devolver valores enviados ni detalles internos.
- `app/static/js/comun.js`: `Fipca.pedir()` convierte esos errores estructurados en un mensaje legible; `Fipca.aviso()` los muestra con SweetAlert2. Los formularios de usuarios y perfil también reúnen los mensajes de expresión regular que ya aparecen junto a cada campo antes de cancelar el envío.
- `app/core/security.py`: política común de fortaleza de contraseñas y funciones de hashing. El inicio de sesión no vuelve a aplicar la política de alta, para no bloquear credenciales existentes.
- `app/api/v1/auth.py`: reglas del flujo que dependen del estado de la cuenta y respuestas HTTP, como el alta inicial del administrador o los conflictos de datos duplicados.
- `app/models/usuario.py` y `init.sql`: consultas y restricciones persistentes de unicidad; estas últimas también protegen frente a solicitudes concurrentes.
- `tests/unit/test_usuario_schema.py` y `tests/integration/test_auth_login.py`, `tests/integration/test_gestion_usuarios.py`: verifican las reglas directamente y a través de la API.

Al añadir un campo, coloque su validación de forma sintáctica en el esquema Pydantic correspondiente y su regla dependiente de base de datos en el flujo/modelo apropiado. No dependa de `expresionesRegulares.js` como control de seguridad ni duplique las mismas reglas en las rutas.

---

## 5. Implementación en el Script de la Vista (`app/static/js/*.js`)

En el archivo JavaScript de tu pantalla (cargado como `<script type="module">`):

```javascript
import { inicializarValidacionFormulario } from "/static/js/expresionesRegulares.js";

(function () {
  "use strict";

  const formulario = document.getElementById("mi-formulario");
  const modalElemento = document.getElementById("mi-modal");
  const modal = modalElemento
    ? window.bootstrap.Modal.getOrCreateInstance(modalElemento)
    : null;

  // 1. Inicializar validador
  const validador = inicializarValidacionFormulario(formulario);

  // 2. Manejar envío
  formulario.addEventListener("submit", async function (evento) {
    evento.preventDefault();

    // Comprobar validez global de todos los campos
    const esValido = validador.verificar();
    if (!esValido) {
      await window.Fipca.aviso(
        null,
        "Por favor, revise los campos marcados en rojo antes de continuar.",
        "error"
      );
      return;
    }

    const boton = formulario.querySelector('button[type="submit"]');
    const giro = boton ? boton.querySelector(".spinner-border") : null;
    const datos = Object.fromEntries(new FormData(formulario).entries());

    if (boton && giro) {
      window.Fipca.cargando(boton, giro, true, "Guardando…");
    }

    try {
      await window.Fipca.pedir("/api/v1/mi-endpoint", {
        metodo: "POST",
        cuerpo: datos,
      });

      if (modal) modal.hide();
      formulario.reset();
      validador.limpiar(); // Limpia marcas verdes/rojas

      await window.Fipca.aviso(null, "Registro exitoso.", "exito");
    } catch (error) {
      await window.Fipca.aviso(null, error.message, "error");
    } finally {
      if (boton && giro) window.Fipca.cargando(boton, giro, false);
    }
  });

  // 3. Resetear formulario y validaciones al abrir/cerrar el modal
  if (modalElemento) {
    modalElemento.addEventListener("hidden.bs.modal", function () {
      formulario.reset();
      validador.limpiar();
    });

    modalElemento.addEventListener("shown.bs.modal", function () {
      const primerCampo = formulario.querySelector(
        'input:not([type="hidden"]):not([disabled])'
      );
      if (primerCampo) primerCampo.focus();
    });
  }
})();
```

---

## 6. Métodos del Validador

`inicializarValidacionFormulario(formulario)` retorna un objeto/función con las siguientes utilidades:

| Método / Propiedad | Tipo | Descripción |
| :--- | :--- | :--- |
| `validador()` o `validador.verificar()` | `Function -> Boolean` | Evalúa de inmediato todos los `.input-validar`. Marca en rojo con su mensaje los campos inválidos o vacíos requeridos. Devuelve `true` si todo es válido o `false` si hay errores. |
| `validador.limpiar()` | `Function` | Elimina todas las clases `.valido`, `.invalido`, oculta los mensajes `.p-error-validaciones` y oculta los iconos `.check` y `.error`. |
| `validador.campos` | `Object` | Diccionario con el estado booleano de cada campo indexado por su atributo `name`. |

---

## 7. Verificación de Accesibilidad y Estilos
- Todos los inputs deben tener su respectivo `<label for="id-del-input">`.
- Los iconos informativos tienen `aria-hidden="true"` para no entorpecer lectores de pantalla.
- Los estilos respetan el modo oscuro (`[data-bs-theme="dark"]`) cambiando los bordes y fondos de validación con tonos adaptados de verde y rojo para un contraste óptimo.

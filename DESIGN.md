---
name: FIPCA Inventario
description: Interfaz web de inventario y asistente RAG de FERRE-INVERSIONES PEREZ C.A.
colors:
  blanco: "#FFFFFF"
  tinta: "#1B2450"
  azul: "#303F76"
  pizarra: "#405080"
  violeta: "#6B46C1"
  violeta-claro: "#805AD5"
  azul-acento: "#2563EB"
  azul-acento-claro: "#7DD3FC"
  azul-acento-hover-claro: "#1D4ED8"
  azul-acento-hover-oscuro: "#38BDF8"
  azul-acento-oscuro: "#7DD3FC"
  cian: "#2CB6C8"
  fondo-claro: "#F4F7FB"
  superficie-claro: "#FFFFFF"
  superficie-alt-claro: "#EEF3F8"
  borde-claro: "#D9E2EC"
  borde-fuerte-claro: "#7B8BA0"
  texto-claro: "#172338"
  texto-suave-claro: "#4A5568"
  fondo-oscuro: "#121B2A"
  superficie-oscuro: "#1B263B"
  superficie-alt-oscuro: "#22334B"
  borde-oscuro: "#35465D"
  borde-fuerte-oscuro: "#6F8097"
  texto-oscuro: "#F2F5FA"
  texto-suave-oscuro: "#C0CBD9"
  accion-superficie-claro: "#EFF6FF"
  accion-borde-claro: "#2563EB"
  accion-texto-claro: "#1D4ED8"
  accion-fondo-claro: "#2563EB"
  accion-boton-texto-claro: "#FFFFFF"
  accion-superficie-oscuro: "#172B4D"
  accion-borde-oscuro: "#60A5FA"
  accion-texto-oscuro: "#BFDBFE"
  accion-fondo-oscuro: "#7DD3FC"
  accion-boton-texto-oscuro: "#10213F"
  violeta-texto-claro: "#573394"
  violeta-superficie-claro: "#F1EDFA"
  violeta-texto-oscuro: "#CFBFFF"
  violeta-superficie-oscuro: "#2B2240"
  azul-superficie-claro: "#303F76"
  azul-superficie-oscuro: "#303F76"
  azul-texto-superficie-claro: "#FFFFFF"
  azul-texto-superficie-oscuro: "#F5F8FF"
  exito-texto-claro: "#2F6B4F"
  exito-superficie-claro: "#EAF4EE"
  exito-borde-claro: "#92ABA4"
  exito-texto-oscuro: "#8FD0AD"
  exito-superficie-oscuro: "#1C2A24"
  exito-borde-oscuro: "#5C7771"
  error-texto-claro: "#A12632"
  error-superficie-claro: "#FFF0EF"
  error-texto-oscuro: "#FFB4AB"
  error-superficie-oscuro: "#401E22"
typography:
  cuerpo:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  boton:
    fontSize: "0.95rem"
    fontWeight: 650
    lineHeight: 1
  titulo-panel:
    fontSize: "1.45rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  titulo-chat:
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  titulo-vacio:
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  rotulo:
    fontSize: "0.72rem"
    fontWeight: 700
    letterSpacing: "0.1em"
  micro:
    fontSize: "0.7rem"
    fontWeight: 600
    letterSpacing: "0.06em"
rounded:
  sm: "6px"
  md: "12px"
  lg: "14px"
  pill: "999px"
spacing:
  esp-1: "4px"
  esp-2: "8px"
  esp-3: "12px"
  esp-4: "16px"
  esp-5: "24px"
  esp-6: "32px"
  esp-7: "48px"
  esp-8: "64px"
components:
  boton-primario:
    backgroundColor: "{colors.accion-fondo-claro}"
    textColor: "{colors.accion-boton-texto-claro}"
    typography: "{typography.boton}"
    rounded: "{rounded.sm}"
    padding: "0 24px"
    height: "44px"
  boton-primario-hover:
    backgroundColor: "{colors.azul-acento-hover-claro}"
  boton-fantasma:
    textColor: "{colors.texto}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "44px"
  campo:
    backgroundColor: "{colors.superficie-claro}"
    textColor: "{colors.texto-claro}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "44px"
  tarjeta:
    backgroundColor: "{colors.superficie-claro}"
    rounded: "{rounded.lg}"
    padding: "24px"
  banda-accion:
    backgroundColor: "{colors.accion-superficie-claro}"
    rounded: "{rounded.lg}"
    padding: "32px"
  chip-neutro:
    backgroundColor: "{colors.superficie-alt-claro}"
    textColor: "{colors.texto-suave-claro}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-listo:
    backgroundColor: "{colors.exito-superficie-claro}"
    textColor: "{colors.exito-texto-claro}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-curso:
    backgroundColor: "{colors.accion-superficie-claro}"
    textColor: "{colors.accion-texto-claro}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
---

# Sistema de diseño: FIPCA Inventario

## Overview

**El mostrador FIPCA.** La interfaz combina fondos claros de matiz azul con
superficies blancas; el modo oscuro usa el azul profundo del identificativo
como base. El cobalto organiza las superficies de conversación y las acciones;
el cian y el violeta quedan como acentos puntuales, sin competir con el catálogo.

El sistema se usa de pie, con clientes esperando, en un PC compartido con la
caja y en una tablet en el depósito. Por eso la densidad es baja, el contraste
alto, los objetivos táctiles grandes y las transiciones cortas. No hay
ilustraciones, ni degradados decorativos, ni animaciones de bienvenida: el
trabajo empieza en la primera línea de texto.

El modo claro no es el modo oscuro invertido: usa superficies blancas y
separadores azulados para el mostrador iluminado; el modo oscuro separa los
planos con azul marino y cobalto. Ambos conservan la misma jerarquía de marca.

Decisiones que la interfaz evita a propósito:

- Fondo crema o beige "acogedor": la base es un neutro azulado tomado del navy
  del identificativo.
- Rejillas de tarjetas iguales como portada: el panel abre con una acción
  concreta y una lista de estado.
- Puntos suspensivos palpitando como "escribiendo": se usa un giro continuo y
  una frase que dice qué está pasando.
- Cristal, sombras de color y bordes de neón: el vidrio esmerilado se limita a
  la barra del chat (`color-mix` al 90 % de la superficie).

## Colors

La paleta de marca sigue `paleta_de_colores_y_gu_a_de_dise_o.md`. Estos colores
no cambian entre temas:

| Token | Valor | Uso |
|---|---|---|
| `blanco` | `#FFFFFF` | Logotipo y texto sobre superficies azules |
| `tinta` | `#1B2450` | Texto principal y fondo de marca |
| `azul` | `#303F76` | Azul profundo para superficies de marca y conversación |
| `pizarra` | `#405080` | Azul pizarra para transiciones y detalles |
| `violeta` | `#6B46C1` | Foco, cursor y selección en tema claro |
| `violeta-claro` | `#805AD5` | Reflejo violeta en el panel de acceso |
| `azul-acento` | `#2563EB` | Acciones principales y enlaces en modo claro |
| `azul-acento-claro` | `#7DD3FC` | Acento de marca y acciones en modo oscuro |
| `cian` | `#2CB6C8` | Detalles puntuales inspirados en la imagen |

Tokens semánticos, con su pareja por tema:

| Rol | Claro | Oscuro |
|---|---|---|
| Fondo | `#F4F7FB` | `#121B2A` |
| Superficie | `#FFFFFF` | `#1B263B` |
| Superficie alterna | `#EEF3F8` | `#22334B` |
| Borde | `#D9E2EC` | `#35465D` |
| Borde de control | `#7B8BA0` | `#6F8097` |
| Texto | `#172338` | `#F2F5FA` |
| Texto suave | `#4A5568` | `#C0CBD9` |
| Superficie de acento | `#EFF6FF` | `#172B4D` |
| Texto de acento | `#1D4ED8` | `#BFDBFE` |
| Violeta | `#573394` sobre `#F1EDFA` | `#CFBFFF` sobre `#2B2240` |
| Éxito | `#2F6B4F` sobre `#EAF4EE` | `#8FD0AD` sobre `#1C2A24` |
| Error | `#A12632` sobre `#FFF0EF` | `#FFB4AB` sobre `#401E22` |
| Azul de superficie | `#303F76` | `#303F76` |
| Azul de texto sobre superficie | `#FFFFFF` | `#F5F8FF` |
| Fondo de acción | `#2563EB` | `#7DD3FC` |
| Texto de acción | `#FFFFFF` | `#10213F` |

Reglas:

- **El azul señala acción.** El cobalto rellena el botón principal en claro; el
  azul cielo conserva el contraste en oscuro.
- **El azul es estructura.** Azul noche, cobalto y pizarra dan jerarquía a las
  superficies y mantienen el carácter ferretero de la marca.
- **El violeta y el cian son acentos.** Se usan en el foco y detalles de marca; no
  reemplaza los colores semánticos de error o éxito.
- **Contraste AA como piso.** Texto normal a 4.5:1 o más, incluidos botones,
  placeholders, texto suave, estados y texto sobre superficies de marca. Los
  bordes de control mantienen al menos 3:1 contra su superficie.
- **Sin crema de fondo.** El modo claro usa un neutro azulado y superficies
  blancas, no un beige ajeno a la guía.

## Typography

Una sola familia: la pila del sistema operativo. No se descarga ninguna fuente,
porque los equipos son de gama baja y la conexión es irregular.

| Rol | Tamaño | Peso | Dónde |
|---|---|---|---|
| Cuerpo | 15 px / 1.55 | 400 | Texto general, formularios, chat |
| Título de panel | 23.2 px | 700 | "Buen día, Ana" |
| Título de chat | 20 px | 700 | Cabecera del asistente |
| Título de estado vacío | 26 px | 700 | "¿Qué necesita del inventario?" |
| Rótulo | 11.5 px, tracking 0.1 em | 700 | "Estado del sistema" |
| Micro | 11.2 px | 600 | Lema de marca, chips |

Reglas:

- **Una sola jerarquía por pantalla.** El `h1` manda; el resto baja en dos
  pasos como máximo. El detector de calidad exige que el salto sea visible.
- **Nada funcional por debajo de 11 px.** Chips, lema y metadatos se quedan en
  11.2 px; el texto legal puede bajar a 10 px.
- **Cifras tabulares.** Precios y existencias usan `font-variant-numeric:
  tabular-nums` para poder compararse en columna.
- **Mayúsculas solo en rótulos cortos.** Nunca en párrafos ni en botones.
- **`text-wrap: balance` en titulares** y `pretty` en párrafos largos cuando el
  navegador lo soporta; sin dependencias.

## Layout

- **Panel:** rejilla de dos columnas, acción principal (1.4 fr) y estado
  (0.6 fr), separadas 32 px. Ancho máximo 1120 px. Por debajo de 900 px pasa a
  una columna.
- **Usuarios:** tabla de cuentas con búsqueda, ordenamiento, paginación y
  expansión responsive; alta y edición ocurren en un modal. Las acciones
  permiten activar o desactivar sin borrar el historial.
- **Perfil:** fotografía, rol y datos personales en una ficha compacta con
  superficies y colores de tema; los cambios de datos y fotografía se realizan
  en un modal con vista previa y validación en vivo.
- **Configuración:** versión y vigencia de sesión para ambos roles; diagnóstico
  de bases y límites de ingesta solo para administración.
- **Asistente:** dos columnas. El panel de fuentes ocupa 292 px a la izquierda y
  la conversación el resto, con el hilo centrado a 780 px y el redactor anclado
  abajo. `body.cuerpo-chat` es flex y `main` crece, sin restar alturas fijas.
- **Acceso (login, recuperación):** dos mitades en escritorio; el panel de marca
  desaparece por debajo de 900 px y el logotipo se traslada sobre el formulario.
  La caja del formulario no supera 400 px.
- **Ritmo:** múltiplos de 4 px (`--esp-1` a `--esp-8`). Los bloques respiran a
  24–32 px; las filas de estado, a 16 px.
- **Puntos de quiebre:** 1150 px (menú hamburguesa antes de que la navegación
  desborde), 900 px (paneles y rejillas) y 640 px (cabecera del chat). En móvil,
  los enlaces quedan dentro del menú desplegable; el panel de fuentes pasa a
  cajón deslizante con velo y se abre desde el botón "Fuentes". Los controles
  de navegación conservan objetivos táctiles de 44 px. A 470 px o menos, los
  campos de todos los formularios se apilan en una columna.
- **Objetivos táctiles:** 44 px mínimos en móvil, incluidos los botones de tema
  y las sugerencias del asistente.

## Elevation & Depth

Dos niveles de sombra, ambos ambientales y muy contenidos:

- `--sombra-1`: `0 1px 2px` + `0 4px 12px` al 6 % y 5 %. Para tarjetas y
  superficies en reposo.
- `--sombra-2`: `0 10px 30px` al 10 % (claro) o `0 14px 40px` al 55 % (oscuro).
  Solo al elevar una tarjeta interactiva al pasar el cursor.

La profundidad principal es **tonal**, no proyectada: superficie blanca sobre
fondo azul claro, o `#1B263B` sobre `#121B2A`. En el modo oscuro la sombra
sirve para separar planos, no para dramatizar.

No hay sombras de color, ni halos, ni `backdrop-filter` salvo el 90 % de
superficie en la cabecera del chat.

## Shapes

- Radios: 6 px en botones, campos y chips cuadrados; 12 px en el redactor; 14 px
  en tarjetas y bandas; 999 px en chips y píldoras.
- Bordes de 1 px como separación principal; nunca 2 px salvo el foco.
- El foco es un anillo de 3 px con `outline-offset: 2px`, violeta sólido en
  claro y azul cielo en oscuro. Es requisito de accesibilidad, no un adorno:
  no se elimina con `outline: none` sin sustituto.
- La línea separadora de las filas de estado es un pseudo-elemento decorativo,
  no un `border-bottom` del contenedor: así el texto nunca queda pegado al filo.

## Components

### Botón principal (`.btn-fipca`)

44 px de alto, relleno azul cobalto en claro y azul cielo en oscuro, texto
contrastante y radio 6 px. Al pasar el cursor cambia al tono azul de interacción;
no cambia de tamaño. Se reserva para la acción principal: "Preguntar", "Entrar",
"Enviar enlace".

### Botón fantasma (`.btn-fipca--fantasma`)

Borde de 1 px, fondo transparente, texto en color normal. Para "Salir" y
acciones secundarias. En móvil mantiene 44 px.

### Campos

Fondo de superficie, borde fuerte de 1 px, radio 6 px, 44 px de alto; el
formulario completo envuelve al campo y se ilumina al recibir el foco (borde
violeta + anillo). El cursor de texto es violeta. Los formularios envían JSON
con `fetch`; no hay envío multipart.

### Tarjetas y bandas

Tarjeta blanca de 14 px de radio con `--sombra-1`; al ser un enlace sube 2 px y
adopta borde azul. La banda de acción del panel usa una superficie azul muy
suave y borde cobalto: es la única superficie teñida de la pantalla.

### Chips de estado

Píldora de 11.2 px con punto de 6 px. Tres variantes: neutra (pendiente),
`--listo` (verde de éxito) y `--curso` (azul, "Provisional"). Nunca se usan como
botones.

### Barra de navegación

Fija arriba, superficie al 90 %, borde inferior de 1 px y 48 px de alto en
escritorio (52 px en móvil por los objetivos táctiles). Contiene marca, enlaces
(Panel, Asistente, Usuarios solo para administradores, Perfil, Configuración y
API solo para administradores), nombre y rol del usuario, conmutador de tema y
salida con icono y nombre accesible. Al ancho de 1150 px el menú de enlaces se
colapsa tras un botón hamburguesa; Escape y un clic fuera lo cierran. El botón
de salida solicita confirmación con SweetAlert2.

### Gestión de cuentas

Las cuentas se presentan con DataTables y su extensión Responsive, búsqueda,
ordenamiento y paginación en español. Alta y edición comparten un modal; la
edición de datos y rol se persiste de manera atómica. Las acciones de estado
solicitan confirmación y nunca ofrecen borrado físico. SweetAlert2 comunica
errores, resultados y decisiones; los campos conservan validación accesible.
Las imágenes se validan en el servidor y se guardan normalizadas como WebP; la
interfaz ofrece vista previa y el avatar local al quitarla.

### Avisos y dependencias locales

SweetAlert2 presenta mensajes de éxito e información como avisos breves y los
errores y confirmaciones como diálogos. Las dependencias JavaScript y sus
estilos se sirven desde `app/static/vendor/`, con versiones fijadas en
`package.json`; la interfaz no depende de un CDN para cargarlos.

### Carga de vistas

Un indicador global en `base.html` cubre brevemente la vista al abrir una
página y al navegar con enlaces internos. Usa un fondo de tema, un aro cobalto
con detalle cian y el mensaje "Cargando vista". Se omite en anclas de la misma
página, enlaces externos, descargas y pestañas nuevas. Las acciones que usan
`fetch` conservan sus propios estados de carga y no muestran este overlay. El
movimiento del aro respeta `prefers-reduced-motion`.

### Burbujas del asistente

Usuario: fondo `--azul-superficie` (`#303F76` en ambos temas),
texto claro, radio 12 px con la esquina inferior derecha a 6 px, alineado a la
derecha. Asistente: superficie blanca, borde de 1 px, avatar violeta de 34 px con
las letras "IA". La respuesta provisional se separa del cuerpo con una línea de
texto suave.

### Panel de fuentes

Columna de 292 px a la izquierda del asistente, inspirada en la biblioteca de
fuentes de NotebookLM. Cabecera con el título, el conteo de archivos y el aspa de
cierre (solo móvil); debajo, el botón "Agregar archivo", una zona punteada para
arrastrar y soltar, y la lista de archivos. Cada archivo muestra una ficha de
extensión en azul (PDF, XLSX, CSV…), el nombre recortado con puntos suspensivos y
su tamaño. El pie declara que la carga es una vista previa hasta la Semana 3. Los
controles de carga solo se renderizan para el rol administrador; el resto ve la
lista y la frase que lo explica.

### Indicador de consulta

Giro circular de 14 px (borde fuerte con el tramo superior en violeta) más la
frase "Consultando el catálogo…". Sin puntos palpitando, sin saltos verticales.
La animación se anula con `prefers-reduced-motion`.

### Animación

Una sola entrada: `entrar-mensaje`, 320 ms con curva expo-out, desplazamiento de
6 px y desenfoque de 2 px. Se aplica a cada mensaje nuevo y a nada más.

## Do's and Don'ts

**Do**

- Usar el azul cobalto para una sola acción principal por pantalla.
- Componer con las variables de `estilos.css`; los valores nuevos entran como
  token, no como literal suelto.
- Probar claro y oscuro, 1440 px y 390 px, antes de dar una pantalla por
  terminada.
- Escribir en español de Venezuela, con tildes y tratamiento de "usted".
- Mantener el foco visible y los 44 px táctiles aunque el diseño "se vea mejor"
  sin ellos.
- Decir la verdad en la interfaz: si el motor es provisional, se declara.

**Don't**

- Volver al fondo crema (`#F6F4EF`) ni a tarjetas blancas sobre beige.
- Usar rejillas de cuatro tarjetas iguales como portada.
- Animar más de una cosa a la vez ni usar puntos suspensivos infinitos.
- Poner texto funcional por debajo de 11 px.
- Inventar productos, precios o cifras de uso: solo lo que existe en la base o
  lo que se declare como ejemplo.
- Añadir dependencias de CDN, fuentes externas o iconos descargados.

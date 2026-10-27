---
name: FIPCA Inventario
description: Interfaz web de inventario y asistente RAG de FERRE-INVERSIONES PEREZ C.A.
colors:
  tinta: "#16141B"
  azul: "#2D3044"
  pizarra: "#3E4053"
  malva: "#544E5B"
  ciruela: "#824F62"
  oro: "#D9C793"
  oro-claro: "#EFE4C3"
  fondo-claro: "#F2F1F5"
  superficie-claro: "#FFFFFF"
  superficie-alt-claro: "#F8F7FA"
  borde-claro: "#E3E0E9"
  borde-fuerte-claro: "#CFCAD6"
  texto-claro: "#1B1922"
  texto-suave-claro: "#56515F"
  fondo-oscuro: "#100E15"
  superficie-oscuro: "#191722"
  superficie-alt-oscuro: "#201D2B"
  borde-oscuro: "#322E40"
  borde-fuerte-oscuro: "#45404F"
  texto-oscuro: "#EFE9DC"
  texto-suave-oscuro: "#ACA5BA"
  oro-superficie-claro: "#F6EFDB"
  oro-borde: "#D9C793"
  oro-texto-claro: "#6B5220"
  oro-superficie-oscuro: "#2A2434"
  oro-texto-oscuro: "#E3D3A4"
  ciruela-texto-claro: "#7A4657"
  ciruela-superficie-claro: "#F9ECEF"
  exito-texto-claro: "#2F6B4F"
  exito-superficie-claro: "#EAF4EE"
  exito-borde-claro: "#92ABA4"
  exito-texto-oscuro: "#8FD0AD"
  exito-superficie-oscuro: "#1C2A24"
  exito-borde-oscuro: "#5C7771"
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
    backgroundColor: "{colors.oro}"
    textColor: "{colors.tinta}"
    typography: "{typography.boton}"
    rounded: "{rounded.sm}"
    padding: "0 24px"
    height: "44px"
  boton-primario-hover:
    backgroundColor: "{colors.oro-claro}"
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
    backgroundColor: "{colors.oro-superficie-claro}"
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
    backgroundColor: "{colors.oro-superficie-claro}"
    textColor: "{colors.oro-texto-claro}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
---

# Sistema de diseño: FIPCA Inventario

## Overview

**El mostrador iluminado.** La interfaz es el mostrador de una ferretería de
barrio a media luz: las superficies son neutras y profundas —violeta grisáceo,
casi tinta— y sobre ellas cae una sola luz cálida, el dorado del identificativo.
Nada más compite por la atención: el oro marca lo que se puede hacer o lo que
hay que mirar, y el resto se mantiene en silencio.

El sistema se usa de pie, con clientes esperando, en un PC compartido con la
caja y en una tablet en el depósito. Por eso la densidad es baja, el contraste
alto, los objetivos táctiles grandes y las transiciones cortas. No hay
ilustraciones, ni degradados decorativos, ni animaciones de bienvenida: el
trabajo empieza en la primera línea de texto.

El modo claro no es el modo oscuro invertido, sino la misma habitación de día.
En ambos, el dorado es el único acento cálido y la ciruela aparece solo como
reflejo (foco, selección, detalle del asistente).

Decisiones que la interfaz evita a propósito:

- Fondo crema o beige "acogedor": el gris violeta viene del identificativo, el
  crema era un reflejo de moda.
- Rejillas de tarjetas iguales como portada: el panel abre con una acción
  concreta y una lista de estado.
- Puntos suspensivos palpitando como "escribiendo": se usa un giro continuo y
  una frase que dice qué está pasando.
- Cristal, sombras de color y bordes de neón: el vidrio esmerilado se limita a
  la barra del chat (`color-mix` al 90 % de la superficie).

## Colors

La paleta se extrae de `paleta.jpg`, la fotografía del identificativo. Los siete
valores de marca no cambian entre temas:

| Token | Valor | Uso |
|---|---|---|
| `tinta` | `#16141B` | Texto sobre dorado, fondo del modo oscuro |
| `azul` | `#39446F` | Azul de marca, aclarado respecto al identificativo para que se lea como azul |
| `pizarra` | `#4A5578` | Violeta grisáceo, un paso más claro que el original |
| `malva` | `#544E5B` | Origen del gris violeta del modo claro |
| `ciruela` | `#824F62` | Reflejo magenta: foco, cursor, asistente |
| `oro` | `#D9C793` | Acento único; relleno del botón principal |
| `oro-claro` | `#EFE4C3` | Brillo del logotipo sobre fondo oscuro |

Tokens semánticos, con su pareja por tema:

| Rol | Claro | Oscuro |
|---|---|---|
| Fondo | `#F2F1F5` | `#100E15` |
| Superficie | `#FFFFFF` | `#191722` |
| Superficie alterna | `#F8F7FA` | `#201D2B` |
| Borde | `#E3E0E9` | `#322E40` |
| Texto | `#1B1922` | `#EFE9DC` |
| Texto suave | `#56515F` | `#ACA5BA` |
| Oro de superficie | `#F6EFDB` | `#2A2434` |
| Oro de texto | `#6B5220` | `#E3D3A4` |
| Éxito | `#2F6B4F` sobre `#EAF4EE` | `#8FD0AD` sobre `#1C2A24` |
| Azul de superficie | `#3B4776` | `#414E82` |
| Azul de texto sobre superficie | `#EFE4C3` | `#F2EAD9` |
| Azul de acento | `#3B4776` | `#9AA8E0` |

Reglas:

- **El dorado no es decorativo.** Rellena el botón principal, marca la banda de
  consulta, los chips en curso y el foco cálido del modo oscuro. Si un elemento
  no se puede accionar ni necesita distinguirse, no lleva oro.
- **El violeta es estructura.** Fondos, superficies y bordes salen del malva,
  no de un gris neutro puro; así el conjunto pertenece al identificativo.
- **El azul se distingue.** El azul del identificativo (`#2D3044`) se aclaró a
  `#39446F` porque en pantalla se leía como negro. Ningún texto blanco baja de
  4.5:1 sobre él.
- **La ciruela es reflejo.** Aparece en el foco (`--anillo`), el cursor de los
  campos y el avatar del asistente, nunca en áreas grandes.
- **Contraste AA como piso.** Texto normal a 4.5:1 o más; el gris suave del
  modo claro (`#56515F`) es el mínimo permitido sobre superficie blanca.
- **Sin crema de fondo.** `#F6F4EF` se descartó: no salía de la paleta y el
  detector de calidad lo marcaba como patrón automático.

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
- **Asistente:** dos columnas. El panel de fuentes ocupa 292 px a la izquierda y
  la conversación el resto, con el hilo centrado a 780 px y el redactor anclado
  abajo. `body.cuerpo-chat` es flex y `main` crece, sin restar alturas fijas.
- **Acceso (login, recuperación):** dos mitades en escritorio; el panel de marca
  desaparece por debajo de 900 px y el logotipo se traslada sobre el formulario.
  La caja del formulario no supera 400 px.
- **Ritmo:** múltiplos de 4 px (`--esp-1` a `--esp-8`). Los bloques respiran a
  24–32 px; las filas de estado, a 16 px.
- **Puntos de quiebre:** 900 px (paneles y rejillas) y 640 px (barra de
  navegación y cabecera del chat). En móvil, el enlace "API" y el lema de marca
  se ocultan; el panel de fuentes pasa a cajón deslizante con velo y se abre
  desde el botón "Fuentes" de la cabecera. Tema y "Salir" conservan 44 px de
  alto.
- **Objetivos táctiles:** 44 px mínimos en móvil, incluidos los botones de tema
  y las sugerencias del asistente.

## Elevation & Depth

Dos niveles de sombra, ambos ambientales y muy contenidos:

- `--sombra-1`: `0 1px 2px` + `0 4px 12px` al 6 % y 5 %. Para tarjetas y
  superficies en reposo.
- `--sombra-2`: `0 10px 30px` al 10 % (claro) o `0 14px 40px` al 55 % (oscuro).
  Solo al elevar una tarjeta interactiva al pasar el cursor.

La profundidad principal es **tonal**, no proyectada: superficie blanca sobre
fondo gris violeta, o `#191722` sobre `#100E15`. En el modo oscuro la sombra
sirve para separar planos, no para dramatizar.

No hay sombras de color, ni halos, ni `backdrop-filter` salvo el 90 % de
superficie en la cabecera del chat.

## Shapes

- Radios: 6 px en botones, campos y chips cuadrados; 12 px en el redactor; 14 px
  en tarjetas y bandas; 999 px en chips y píldoras.
- Bordes de 1 px como separación principal; nunca 2 px salvo el foco.
- El foco es un anillo de 3 px con `outline-offset: 2px`, en ciruela translúcida
  (claro) o dorado translúcido (oscuro). Es requisito de accesibilidad, no un
  adorno: no se elimina con `outline: none` sin sustituto.
- La línea separadora de las filas de estado es un pseudo-elemento decorativo,
  no un `border-bottom` del contenedor: así el texto nunca queda pegado al filo.

## Components

### Botón principal (`.btn-fipca`)

44 px de alto, relleno dorado con degradado vertical de `#E4D5A6` a `--oro`,
texto en tinta, radio 6 px. Al pasar el cursor sube el brillo un 5 %; no cambia
de tamaño. Es la única acción dorada de la pantalla: "Preguntar", "Entrar",
"Enviar enlace".

### Botón fantasma (`.btn-fipca--fantasma`)

Borde de 1 px, fondo transparente, texto en color normal. Para "Salir" y
acciones secundarias. En móvil mantiene 44 px.

### Campos

Fondo de superficie, borde fuerte de 1 px, radio 6 px, 44 px de alto; el
formulario completo envuelve al campo y se ilumina al recibir el foco (borde
ciruela + anillo). El cursor de texto es ciruela. Los formularios envían JSON
con `fetch`; no hay envío multipart.

### Tarjetas y bandas

Tarjeta blanca de 14 px de radio con `--sombra-1`; al ser un enlace sube 2 px y
adopta borde dorado. La banda de acción del panel usa un degradado suave de oro
de superficie a blanco (160°) y borde dorado: es la única superficie teñida de
la pantalla.

### Chips de estado

Píldora de 11.2 px con punto de 6 px. Tres variantes: neutra (pendiente),
`--listo` (verde de éxito) y `--curso` (oro, "Provisional"). Nunca se usan como
botones.

### Barra de navegación

Fija arriba, superficie al 90 %, borde inferior de 1 px y 48 px de alto en
escritorio (52 px en móvil por los objetivos táctiles). Contiene marca, enlaces
(Panel, Asistente, API solo para administradores), nombre y rol del usuario,
conmutador de tema y "Salir". En móvil pierde el texto de marca, el lema y el
enlace API.

### Burbujas del asistente

Usuario: fondo `--azul-superficie` (`#3B4776` en claro, `#414E82` en oscuro),
texto claro, radio 12 px con la esquina inferior derecha a 6 px, alineado a la
derecha. Asistente: superficie blanca, borde de 1 px, avatar ciruela de 34 px con
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

Giro circular de 14 px (borde fuerte con el tramo superior en ciruela) más la
frase "Consultando el catálogo…". Sin puntos palpitando, sin saltos verticales.
La animación se anula con `prefers-reduced-motion`.

### Animación

Una sola entrada: `entrar-mensaje`, 320 ms con curva expo-out, desplazamiento de
6 px y desenfoque de 2 px. Se aplica a cada mensaje nuevo y a nada más.

## Do's and Don'ts

**Do**

- Usar el dorado para una sola acción por pantalla.
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

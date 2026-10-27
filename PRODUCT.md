# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Dos roles reales, definidos en los requisitos del cliente:

- **Administrador** (dueño o encargado): da de alta cuentas, carga catálogos de
  proveedores, ajusta inventario y revisa la auditoría. Trabaja en la oficina del
  local, en un PC de escritorio, con el catálogo del proveedor a mano en Excel,
  Word o PDF.
- **Ventas** (vendedor de mostrador): atiende clientes de pie, entre una consulta
  y otra, y necesita saber si hay stock, cuánto cuesta y dónde está. Usa el mismo
  PC del mostrador y, cuando va al depósito, una tablet o un celular.

El trabajo a resolver es siempre el mismo: responder "¿tiene esto?, ¿cuánto
cuesta?, ¿cuántos quedan?" sin caminar al depósito ni abrir el archivo del
proveedor.

## Product Purpose

Sistema web de gestión de inventario con un asistente de IA que responde en
lenguaje natural **solo** sobre los productos registrados en la base de la
ferretería. Existe para que una consulta de mostrador se resuelva en segundos y
para que toda modificación quede atribuida a una persona.

El éxito se mide en dos cosas: la consulta se responde sin salir del mostrador, y
cada cambio de precio, stock o usuario tiene nombre, fecha y hora.

## Positioning

La respuesta no la inventa un modelo: se recupera del catálogo real del negocio
(búsqueda vectorial sobre descripciones de productos) y se devuelve junto con los
productos que la respaldan. Un competidor puede copiar el chat; lo que no puede
copiar es el catálogo cargado desde los archivos de sus propios proveedores ni la
bitácora inmutable que registra quién tocó qué.

## Operating Context

- Mostrador de ferretería con luz fluorescente, clientes esperando y sesiones
  cortas; el sistema se abre y se cierra varias veces al día.
- El PC del mostrador comparte espacio con la caja: la ventana del navegador no
  siempre está maximizada.
- En el depósito se usa tablet o celular, de pie y con una sola mano.
- Los catálogos llegan como archivos de proveedores (Excel, CSV, Word, PDF), no
  como una API.
- La jornada empieza con el administrador revisando stock bajo y termina con la
  caja cerrada; la auditoría se consulta cuando algo no cuadra.
- El cliente es venezolano: los montos se muestran en bolívares con separador de
  miles y el IVA está fijado en 16 %.

## Capabilities and Constraints

Implementado y verificado al momento de escribir esto: autenticación con JWT y
roles, recuperación de contraseña por enlace de un solo uso, auditoría inmutable
en `bitacora`, y una vista de asistente que funciona de punta a punta con un
motor provisional (el RAG real llega en la Semana 5 del cronograma).

Restricciones durables:

- Dos bases PostgreSQL separadas: catálogo (`ferreteria_rag`) y usuarios
  (`ferreteria_usuarios`).
- IVA fijo en 16 % con restricción en la base; no se edita desde la interfaz.
- El stock mínimo es un umbral global: el cliente eliminó la columna por
  redundante.
- Sin servidor de correo propio: el enlace de recuperación se escribe en el log
  del servidor (modo consola) hasta que se configure SMTP.
- Equipos de gama baja y conectividad irregular: nada de recursos pesados ni
  dependencias que exijan conexión a un CDN.
- La respuesta del asistente nunca puede salir del catálogo ni mostrar productos
  que no existan en la base.

Pendiente y explícitamente no decidido: catálogo real de productos, política de
stock mínimo por categoría y proveedor de correo definitivo.

## Brand Commitments

- Nombre comercial: **FERRE-INVERSIONES PEREZ C.A.**, marca **FIPCA**, RIF
  J-29775553-5.
- El identificativo del cliente (`paleta.jpg`) es la referencia de color
  vinculante: azul profundo con un rayo magenta y el logotipo en dorado crema.
  El cliente pidió expresamente guiarse por esa paleta, en modo claro y oscuro.
- El logotipo en uso es una vectorización de los tres hexágonos del
  identificativo; no es el archivo original del cliente y debe reemplazarse
  cuando lo entregue en vector.
- Idioma de toda la interfaz: español de Venezuela, tratamiento de "usted".

## Evidence on Hand

- Requisitos funcionales y no funcionales del cliente en `prompts/`.
- Esquema real de la base en `init.sql`, con datos semilla de roles.
- Identificativo fotografiado en `paleta.jpg` (referencia de color y forma).
- Diagrama entidad-relación del cliente en `MER sistema.png`.
- Ausencias que no se deben rellenar con invención: **no hay catálogo real de
  productos todavía**, ni precios, ni testimonios, ni métricas de uso. Cualquier
  cifra mostrada en la interfaz debe provenir de la base o declararse como
  ejemplo.

## Product Principles

1. **La respuesta viene del catálogo, no del modelo.** Si no está en la base, se
   dice que no está; nunca se improvisa un producto ni un precio.
2. **Quien consulta está atendiendo a alguien.** Cada pantalla se resuelve en
   pocos segundos y con el teclado, sin pasos decorativos.
3. **Todo cambio tiene dueño.** La interfaz nunca oculta quién hizo qué ni ofrece
   borrar el rastro.
4. **El sistema se lee en el local, no en una oficina ideal.** Contraste alto,
   tipografía nítida, funciona con luz fuerte, pantalla sucia y una mano libre.

## Accessibility & Inclusion

- Contraste mínimo AA (4.5:1 en texto normal), foco visible en todos los
  controles y recorrido completo por teclado.
- Modo claro y oscuro con la preferencia del sistema como valor inicial.
- Respeto por `prefers-reduced-motion`.
- Objetivos táctiles de al menos 44 px para el uso en tablet y celular.

# Acta Adenda 1 — Interfaz Web Anticipada

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario con Inteligencia Artificial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Semana 2.5 (Adenda 1) |
| **Fecha de entrega** | 27 de octubre de 2026 |
| **Estado** | Entregado y verificado |

---

## 1. Resumen para la gerencia

A pedido del cliente, se adelantó **la cara visible del sistema** antes de
comenzar la carga de catálogos. Hasta la semana pasada el sistema tenía puerta y
cerradura, pero no tenía mostrador: se podía entrar por la API, no por una
pantalla.

Esta adenda entrega cuatro pantallas y el flujo completo de acceso. Un vendedor
ya puede entrar, escribir una pregunta y recibir una respuesta con el mismo
formato que tendrá el asistente definitivo. Lo que falta es el motor que busca
en el catálogo, que corresponde a la Semana 5.

**En palabras sencillas:**

- **Se entra por una pantalla normal**, con usuario y contraseña, sin escribir
  direcciones técnicas ni copiar tokens.
- **Si se olvida la contraseña, hay un enlace de recuperación** que llega por
  correo (o se escribe en el registro del servidor mientras no haya correo
  configurado). El enlace sirve una sola vez, durante 30 minutos.
- **El panel abre con la pregunta, no con un menú.** El primer gesto después de
  entrar es escribir lo que se necesita del inventario; el resto del panel
  informa el estado del sistema y de la cuenta.
- **El asistente responde hoy con un aviso honesto**: dice que el catálogo aún
  no está vectorizado y que el motor llega en la Semana 5. No inventa productos.
- **Se ve bien de día y de noche.** El modo inicial sigue la preferencia del
  equipo; el conmutador permite cambiarlo y la elección se recuerda.
- **Funciona en el PC del mostrador y en el celular del depósito.** En una
  pantalla de 390 px no hay desbordes y los botones conservan 44 px de alto.

**Resultado de la verificación:** se ejecutaron **329 controles automáticos**
(98 nuevos en esta adenda) y todos resultaron conformes. El revisor automático
de calidad visual no encontró ningún patrón problemático en acceso, panel ni
asistente, en escritorio y en móvil.

**Inversión de tiempo:** media semana, conforme al ajuste acordado.

---

## 2. Qué puede hacer el usuario ahora

| Pantalla | Dirección | Para qué sirve |
|---|---|---|
| Acceso | `/login` | Entrar con usuario o correo y contraseña |
| Recuperación | `/recuperar` | Pedir el enlace de restablecimiento |
| Nueva contraseña | `/restablecer?token=…` | Definir la contraseña con el enlace recibido |
| Panel | `/dashboard` | Preguntar al inventario y ver el estado del sistema |
| Asistente | `/chat` | Conversar con el asistente y ver las fuentes |

El recorrido del vendedor es siempre el mismo: entra, escribe la pregunta en el
panel y el asistente la recibe ya escrita. Desde el panel también se puede
preguntar por "productos con stock" o "productos por debajo del mínimo" con un
clic, sin escribir.

El asistente conserva la conversación mientras la pestaña está abierta, muestra
el indicador "Consultando el catálogo…" mientras espera y presenta cada respuesta
con una tarjeta por producto cuando el motor real empiece a devolver resultados.

---

## 3. Cómo se ve

La paleta se extrajo de `paleta.jpg`, la fotografía del identificativo: azul
profundo, violeta grisáceo, ciruela del rayo y dorado del logotipo.

- **Modo claro:** fondo gris violeta (`#F2F1F5`), superficies blancas y dorado
  como único acento cálido. Se descartó el fondo crema inicial porque no venía
  del identificativo.
- **Modo oscuro:** fondo casi tinta (`#100E15`), superficies violáceas y el mismo
  dorado, ahora más luminoso.
- **Azul legible:** el azul del identificativo se aclaró de `#2D3044` a
  `#39446F` (y `#414E82` en oscuro) porque en pantalla se confundía con el
  negro. Las burbujas del usuario y las fichas de archivo se leen azules.
- **Panel de fuentes:** el asistente se organiza como NotebookLM, con una
  columna de archivos a la izquierda (agregar, arrastrar, quitar) y la
  conversación a la derecha. En el teléfono el panel es un cajón.
- **Marca:** los tres hexágonos vectorizados, el nombre FIPCA y el lema
  "FERRE-INVERSIONES PEREZ". El logotipo disponible es una vectorización; se
  reemplazará cuando el cliente entregue el archivo original en vector.
- **Tipografía:** la del sistema operativo. No se descarga ninguna fuente, para
  no depender de la conexión ni castigar equipos de gama baja.
- **Bootstrap 5.3.3** se sirve desde el propio proyecto (`app/static/vendor/`);
  no hay CDN.

El sistema de diseño completo está documentado en `DESIGN.md`, en la raíz del
repositorio, con los colores, la escala tipográfica, el ritmo de espaciado y las
reglas de uso de cada componente.

---

## 4. Decisiones tomadas con el cliente

| Tema | Decisión |
|---|---|
| Recuperación de contraseña | Enlace por SMTP; mientras no haya servidor de correo, el enlace se escribe en el registro del servidor (modo consola) |
| Sesión en el navegador | JWT en cookie `HttpOnly`, `SameSite=Lax`, más CSRF de doble envío |
| Contrato del asistente | Se publica `POST /api/v1/rag/chat` con el contrato final desde ahora; el contenido es provisional |
| Imagen Docker | Se construye al final de la adenda, después de estabilizar la interfaz |
| Formularios | Envío en JSON con `fetch`; no se añadió `python-multipart` |

---

## 5. Seguridad aplicada en esta etapa

- **La cookie de sesión no es legible por JavaScript** (`HttpOnly`) y no viaja
  en peticiones de otros sitios (`SameSite=Lax`). El encabezado
  `Authorization` sigue funcionando para la API.
- **CSRF de doble envío:** cada formulario lee la cookie `csrf_token` y la envía
  en el encabezado `X-CSRF-Token`. El servidor compara ambos valores y, además,
  valida el origen de la petición cuando el navegador lo informa.
- **El enlace de recuperación** se genera con 32 bytes aleatorios, se guarda
  solo su huella SHA-256, dura 30 minutos, sirve una sola vez e invalida
  cualquier enlace anterior. La respuesta es siempre la misma, exista o no la
  cuenta, para no revelar qué correos están registrados.
- **Límite de intentos:** cinco solicitudes cada quince minutos por dirección IP
  (en memoria, suficiente para una sola instancia).
- **El chat no interpreta HTML.** Las respuestas y los productos se insertan como
  texto, no como marcado, y la pregunta se valida a 2000 caracteres.
- **La bitácora sigue registrando** cada inicio de sesión, cada intento fallido y
  cada error, sin cambios en su inmutabilidad.

---

## 6. Verificación

### 6.1 Pruebas automáticas

```bash
venv\Scripts\python.exe -m pytest tests/ -q
# 329 passed
```

Las 98 pruebas nuevas cubren:

| Área | Archivo | Qué comprueba |
|---|---|---|
| Tokens de recuperación | `tests/unit/test_recuperacion_tokens.py` | Generación, hash, caducidad, uso único, límite de intentos |
| Acceso web | `tests/integration/test_web_login.py` | HTML, cookie, CSRF, redirecciones y cierre de sesión |
| Recuperación | `tests/integration/test_recuperacion.py` | Flujo completo y respuestas uniformes |
| Asistente web | `tests/integration/test_web_chat.py` | Contrato del chat, panel de fuentes por rol, validación y renderizado |
| CSRF | `tests/security/test_csrf.py` | Peticiones sin token, con token ajeno y con origen distinto |
| Pool de conexiones | `tests/unit/test_pool_conexiones.py` | Descarte de conexiones cerradas por PostgreSQL |
| Imagen Docker | `tests/security/test_compose_hardening.py` | Tres servicios, `no-new-privileges`, solo lectura, usuario sin privilegios y `.dockerignore` |

### 6.2 Revisión en navegador

Se recorrió el flujo completo en Chromium: acceso, panel, asistente, cierre de
sesión, solicitud de recuperación, apertura del enlace del registro y
restablecimiento de la contraseña. Se revisaron las cinco pantallas en modo
claro y oscuro, a 1440 px y a 390 px, sin desbordes horizontales.

### 6.3 Calidad visual

El revisor `impeccable` se ejecutó sobre el acceso, el panel y el asistente
(escritorio y móvil): **0 hallazgos**. En el camino corrigió seis defectos
reales: texto funcional por debajo de 11 px, relleno apretado en la lista de
estado, jerarquía tipográfica plana en el chat, puntos palpitando sin
información, contraste del pie de marca y desborde de la barra en móvil.

### 6.4 Usuario de revisión

En la base **de desarrollo** se creó un usuario de prueba para que el cliente
pueda ver las pantallas: `demo` / `DemoFipca2026` (rol administrador, correo
`demo@ferreteria.local`). No forma parte de la entrega y se elimina antes de
publicar el sistema.

### 6.5 Imagen Docker

La aplicación se empaquetó en `ferreteria-api:2.5` (Python 3.12 slim) y se
verificó en un contenedor conectado a la red de Compose:

| Comprobación | Resultado |
|---|---|
| `/salud` | 200, ambas bases operativas |
| `/login`, `/docs` | 200 |
| `/static/css/estilos.css`, `/static/vendor/bootstrap.min.css` | 200 |
| Usuario del proceso | `uid 10001`, sin privilegios |
| `healthcheck` de Docker | Contenedor marcado como `healthy` |
| `docker compose config` | Válido |

El servicio `api` queda declarado en `docker-compose.yml` con el sistema de
archivos en solo lectura, `/tmp` en memoria y `no-new-privileges`. La imagen no
contiene `.env`, pruebas, capturas ni credenciales: la configuración entra por
variables de entorno.

### 6.6 Ajustes pedidos en la revisión

Después de la primera revisión con el cliente se corrigieron cuatro puntos de la
interfaz:

| Pedido | Resultado |
|---|---|
| Menú menos grueso | La barra baja de 68 px a 51 px; el logotipo y el botón de salida se ajustan sin perder los 44 px táctiles en el teléfono |
| Redactor menos grueso | La caja de escritura baja de 144 px a 91 px en el teléfono y a 91 px en escritorio; el aviso de error ya no reserva alto vacío |
| Azul más claro | `#2D3044` pasa a `#39446F` en claro y `#414E82` en oscuro; se lee azul y no negro, con texto a 6.7:1 o más |
| Sección de archivos | Panel de fuentes a la izquierda del asistente, al estilo de NotebookLM: agregar, arrastrar, listar y quitar archivos |

El panel de fuentes es **solo interfaz**: valida extensión y tamaño (PDF, Excel,
CSV, Word o TXT, hasta 20 MB y 20 archivos), permite arrastrar y soltar, lista
los archivos con su tamaño y los quita de la lista, pero no envía nada al
servidor. Así queda listo el armazón de la Semana 3. Los controles de carga solo
se muestran al rol administrador; ventas ve la lista y la explicación.

Se verificó en Chromium a 1440 px y 390 px, en claro y oscuro: sin desbordes
horizontales, sin errores de consola y con el cajón de fuentes abriendo y
cerrando con el botón, el velo y la tecla Escape.

---

## 7. Entregables de esta adenda

| Archivo | Estado |
|---|---|
| `templates/base.html`, `_marca.html`, `_navbar.html` | Nuevos |
| `templates/login.html`, `recuperar.html`, `restablecer.html` | Nuevos |
| `templates/dashboard.html`, `chat_rag.html` | Nuevos |
| `app/static/css/estilos.css` | Nuevo (sistema de diseño completo) |
| `app/static/js/comun.js`, `tema.js`, `login.js`, `recuperar.js`, `restablecer.js`, `dashboard.js`, `chat.js`, `fuentes.js` | Nuevos |
| `app/static/img/favicon.svg`, `app/static/vendor/bootstrap.min.css` | Nuevos |
| `app/api/v1/web.py` | Nuevo (páginas HTML) |
| `app/api/v1/rag_chat.py` | Nuevo (contrato del asistente) |
| `app/api/v1/auth.py` | Cookies, CSRF, recuperación y cierre de sesión |
| `app/api/deps.py` | Acepta encabezado o cookie |
| `app/core/sesion.py` | Nuevo (cookies y validación de origen) |
| `app/services/email_service.py`, `recuperacion_service.py` | Nuevos |
| `app/models/usuario.py`, `app/models/recuperacion.py`, `app/schemas/usuario_schema.py` | Tokens de recuperación |
| `scripts/migracion_2_5.sql`, `init.sql` | Tabla `tokens_recuperacion` y permisos |
| `app/config.py`, `.env.example`, `requirements.txt` | SMTP, cookies y `jinja2` |
| `Dockerfile`, `.dockerignore`, `docker-compose.yml` | Imagen `ferreteria-api:2.5` y servicio `api` |
| `DESIGN.md`, `PRODUCT.md` | Nuevos |
| `tests/` (6 archivos nuevos y endurecimiento de Docker ampliado) | 98 pruebas |
| `.impeccable/review/` | Capturas claro/oscuro y escritorio/móvil |

---

## 8. Lo que viene

La **Semana 3** comienza el motor de carga de catálogos: leer archivos de
proveedores (PDF, Excel, Word, CSV), limpiar los datos y guardarlos en
PostgreSQL. Antes de escribir código hacen falta cuatro confirmaciones del
cliente:

1. ¿Los PDF de proveedores son **solo texto** o también escaneados?
2. Al repetir un `codigo`, ¿se **actualiza** el producto existente o se rechaza?
3. ¿Se guardan los archivos originales en `uploads/` como respaldo?
4. La prueba de estrés, ¿se reduce a **20 archivos** en lugar de 100?

Ninguna de las cuatro bloquea la interfaz entregada; sí condicionan el diseño
del ETL.

---

## 9. Recomendaciones

- **Configurar el correo antes de la entrega final.** Mientras no exista SMTP, el
  enlace de recuperación aparece en el registro del servidor: sirve para
  operar, no para producción.
- **Publicar con HTTPS.** El sistema no debe salir a internet sin certificado;
  la cookie de sesión viaja en cada petición.
- **Entregar el logotipo original en vector.** La versión actual es una
  vectorización fiel de los tres hexágonos, pero no es el archivo del cliente.
- **Cambiar la contraseña del usuario de prueba o eliminarlo** antes de abrir el
  sistema al personal.

---

## 10. Conformidad

La Adenda 1 se entrega completa: las cuatro pantallas funcionan, el flujo de
recuperación está probado de punta a punta, la API del asistente responde con el
contrato final y la suite automática permanece en verde. El motor de respuestas
y la carga del catálogo continúan según el cronograma original.

---

## Anexo técnico

### A.1 Rutas web

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/login` | Formulario de acceso |
| GET | `/recuperar` | Solicitud de enlace |
| GET | `/restablecer?token=…` | Formulario de nueva contraseña |
| GET | `/dashboard` | Panel (requiere sesión) |
| GET | `/chat` | Asistente (requiere sesión) |

### A.2 Rutas de API usadas por la interfaz

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/v1/auth/login` | Inicia sesión y emite cookie + token |
| POST | `/api/v1/auth/logout` | Borra la cookie de sesión |
| POST | `/api/v1/auth/recuperar` | Solicita el enlace |
| POST | `/api/v1/auth/restablecer` | Cambia la contraseña con el token |
| GET | `/api/v1/auth/me` | Datos de la cuenta en sesión |
| POST | `/api/v1/rag/chat` | Pregunta al asistente |
| GET | `/api/v1/rag/estado` | Disponibilidad del motor RAG |

### A.3 Tabla nueva

```sql
CREATE TABLE IF NOT EXISTS tokens_recuperacion (
    id            SERIAL PRIMARY KEY,
    id_usuario    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash    CHAR(64) NOT NULL UNIQUE,
    expira_en     TIMESTAMPTZ NOT NULL,
    usado_en      TIMESTAMPTZ,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

La migración (`scripts/migracion_2_5.sql`) es idempotente y no borra datos. El
mismo bloque está en `init.sql` para las instalaciones nuevas.

### A.4 Modo consola del correo

Sin SMTP configurado, `email_service` escribe el enlace en el registro:

```text
SMTP no configurado: enlace de recuperacion para demo@ferreteria.local -> http://127.0.0.1:8000/restablecer?token=…
```

Con `SMTP_HOST`, `SMTP_PUERTO`, `SMTP_USUARIO`, `SMTP_PASSWORD`,
`SMTP_REMITENTE` y `SMTP_TLS` definidos en `.env`, el envío es real y el enlace
deja de aparecer en el log.

### A.5 Variables nuevas

| Variable | Para qué |
|---|---|
| `URL_BASE` | Construir el enlace de recuperación con el origen correcto |
| `COOKIE_NOMBRE`, `COOKIE_CSRF` | Nombres de las cookies de sesión y CSRF |
| `COOKIE_SEGURA` | Exigir HTTPS para la cookie (vacío = automático) |
| `RECUPERACION_*` | Vigencia del enlace y límite de solicitudes por IP |
| `SMTP_*` | Servidor de correo saliente |
| `API_HOST_PORT` | Puerto publicado del contenedor `api` |

`JWT_SECRET`, los DSN y `APP_DB_PASSWORD` siguen siendo obligatorios.

### A.6 Decisiones de implementación

- **Sin `python-multipart`:** los formularios envían JSON con `fetch`; el
  servidor no procesa `multipart/form-data` en esta etapa.
- **Sin CDN:** Bootstrap se versiona dentro de `app/static/vendor/`.
- **Una sola animación:** `entrar-mensaje` (320 ms, expo-out) y se desactiva con
  `prefers-reduced-motion`. El indicador de consulta es un giro continuo.
- **Tokens por variable CSS:** ningún color nuevo se escribe como literal suelto
  en los componentes; los valores viven en `:root` y en los temas.

### A.7 Limitaciones conocidas

| Limitación | Impacto | Mitigación prevista |
|---|---|---|
| Motor RAG provisional | El asistente no responde sobre productos | Semanas 4 y 5 |
| Sin límite global de peticiones | Fuerza bruta fuera del login | Middleware de cuotas en Semana 6 |
| El cierre de sesión no revoca el JWT | El token vive hasta su `exp` | Lista de revocación o tokens cortos |
| Sin HTTPS en desarrollo | La cookie viaja en claro en red local | TLS obligatorio al desplegar |
| Sin SMTP configurado | El enlace queda en el registro | Configurar correo antes de producción |
| Logotipo vectorizado | No es el archivo original del cliente | Reemplazo cuando se reciba |

### A.8 Despliegue con Docker

```bash
docker compose up -d --build     # PostgreSQL + pgAdmin + API
docker compose ps
docker compose logs -f api
```

| Elemento | Detalle |
|---|---|
| Imagen | `ferreteria-api:2.5`, basada en `python:3.12-slim` |
| Usuario | `ferreteria`, `uid 10001`, sin shell ni privilegios |
| Sistema de archivos | `read_only: true`, salvo `/tmp` (tmpfs) |
| Puerto | `${BIND_ADDRESS:-127.0.0.1}:${API_HOST_PORT:-8000}:8000` |
| Salud | `HEALTHCHECK` cada 30 s contra `/salud` |
| Configuración | Variables de entorno; ningún `.env` dentro de la imagen |
| Contexto excluido | `.env`, `venv/`, `tests/`, `docs/`, `prompts/`, `.impeccable/`, imágenes |

Si el puerto 8000 está ocupado por la API de desarrollo, ajusta
`API_HOST_PORT` y `URL_BASE` en `.env` antes de levantar el contenedor.

---

*Documento generado como parte del entregable de la Adenda 1 (Semana 2.5).*

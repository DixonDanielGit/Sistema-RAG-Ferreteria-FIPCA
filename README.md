# Sistema Web de Gestión de Inventario e IA RAG

Aplicación web para **FERRE-INVERSIONES PEREZ C.A.** que combina gestión de
inventario con un asistente basado en RAG (Retrieval-Augmented Generation)
sobre el catálogo real de productos.

- **Backend:** Python 3.11+ / FastAPI / Uvicorn / Pydantic
- **Base de datos:** PostgreSQL 16 + `pgvector`
- **Frontend:** Jinja2 + Bootstrap 5 + JavaScript vanilla (fetch/AJAX)
- **IA:** modelo de embeddings + modelo generativo (Semana 4/5)
- **Infraestructura:** Docker + Docker Compose

> Estado actual: **Semana 2.5 (Adenda 1) completada** — infraestructura, base
> de datos, autenticación JWT, auditoría y la interfaz web (acceso, recuperación
> de contraseña, panel y asistente con motor provisional). Las semanas 3 a 8
> añaden ETL, vectores, RAG definitivo, módulos administrativos y despliegue.

## Requisitos

- Docker Desktop con Docker Compose
- Python 3.11 o superior
- Git

## Puesta en marcha

```bash
# 1. Crear la configuración local a partir de la plantilla
cp .env.example .env
#    Edita .env y cambia TODAS las contraseñas y JWT_SECRET por valores propios

# 2. Instalar dependencias en el entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / WSL / macOS
pip install -r requirements.txt

# 3. Levantar PostgreSQL + pgAdmin
docker compose up -d

# 4. Arrancar la API
uvicorn app.main:app --reload
```

| Servicio | URL | Credenciales |
|---|---|---|
| Aplicación (acceso) | http://localhost:8000/login | Usuario y contraseña de la base |
| Panel | http://localhost:8000/dashboard | Requiere sesión |
| Asistente | http://localhost:8000/chat | Requiere sesión |
| API (Swagger UI) | http://localhost:8000/docs | — |
| Estado del servicio | http://localhost:8000/salud | — |
| pgAdmin | http://localhost:8080 | `PGADMIN_DEFAULT_*` de `.env` |
| PostgreSQL | `localhost:5432` | `POSTGRES_*` de `.env` |

Generar un `JWT_SECRET` propio:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Levantar la aplicación en Docker

El `Dockerfile` construye la misma API que se ejecuta con `uvicorn`, sin
necesidad de instalar Python ni las dependencias en el equipo:

```bash
docker compose up -d --build          # PostgreSQL, pgAdmin y API
docker compose ps                     # deben verse los tres servicios
docker compose logs -f api            # registro de la aplicación
```

| Detalle | Valor |
|---|---|
| Imagen | `ferreteria-api:2.5` (Python 3.12 slim) |
| Contenedor | `api_ferreteria`, usuario sin privilegios `uid 10001` |
| Puerto | `API_HOST_PORT` de `.env` (8000 por defecto), solo en `BIND_ADDRESS` |
| Origen público | `URL_BASE` de `.env`, debe coincidir con la barra del navegador |
| Salud | `healthcheck` sobre `/salud` cada 30 s |
| Disco | Solo lectura (`read_only`) con `/tmp` en memoria |

Dos avisos:

- **Cambia `API_HOST_PORT` si el 8000 está ocupado** (por ejemplo, porque la API
  de desarrollo sigue corriendo con `uvicorn`). El puerto del contenedor no
  cambia; solo el publicado en el equipo.
- **`URL_BASE` debe ser el origen real** con el que se abre el sistema. Si el
  puerto publicado es 8099, `URL_BASE=http://localhost:8099`; de lo contrario el
  enlace de recuperación apunta al puerto equivocado y el CSRF rechaza los
  formularios con 403.

Para detener solo la aplicación:

```bash
docker compose stop api
docker compose rm -f api
```

### Crear la primera cuenta

Mientras no exista ningún usuario, el alta está abierta: la primera cuenta
**debe** ser administradora (es el arranque del sistema). Después, solo un
administrador autenticado puede registrar cuentas.

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "cedula": "V-12345678",
    "nombre": "Dixon",
    "apellido": "Bastias",
    "usuario": "admin",
    "correo": "admin@ferreteria.com",
    "password": "ClaveSegura2026",
    "rol": "admin"
  }'
```

### Iniciar sesión

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identificador": "admin", "password": "ClaveSegura2026"}'
```

La respuesta trae `access_token`. Para usarlo:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

En Swagger UI también puedes pulsar **Authorize** y pegar el token.

### Interfaz web

La aplicación sirve las pantallas desde el mismo proceso. Al iniciar sesión en
`/login`, el servidor deja el JWT en una cookie `HttpOnly` y un token CSRF en
una cookie legible; no hay que copiar nada a mano.

| Ruta | Descripción |
|---|---|
| `/login` | Acceso con usuario o correo |
| `/recuperar` | Solicitud del enlace de restablecimiento |
| `/restablecer?token=…` | Nueva contraseña con el enlace recibido |
| `/dashboard` | Panel: preguntar al inventario y estado del sistema |
| `/chat` | Asistente de inventario con el panel de fuentes |

El panel y el asistente se adaptan a escritorio y móvil, y siguen el tema del
sistema operativo (claro u oscuro) hasta que se cambie con el conmutador.

**Panel de fuentes.** A la izquierda del asistente vive la lista de archivos que
alimentan al catálogo: PDF, Excel, CSV, Word o TXT. En esta etapa es solo
interfaz. El administrador puede agregarlos, arrastrarlos y quitarlos de la
lista, pero nada se envía al servidor; la carga real llega con el ETL de la
Semana 3. El rol de ventas ve la lista y una frase que explica quién puede
cargarla. En el teléfono el panel se abre como cajón desde el botón "Fuentes".

**Recuperación sin SMTP.** Mientras `SMTP_HOST` no esté configurado, el enlace
de recuperación se escribe en el registro de Uvicorn:

```text
Enlace de recuperacion para demo@ferreteria.local:
http://127.0.0.1:8000/restablecer?token=…
```

El enlace dura 30 minutos, sirve una sola vez y anula cualquier enlace anterior.
Con las variables `SMTP_*` definidas en `.env`, el envío pasa a ser por correo y
el enlace deja de aparecer en el log.

**Sesión por cookie y CSRF.** Además del encabezado `Authorization`, la API
acepta la cookie de sesión. Toda petición que modifique datos debe enviar el
encabezado `X-CSRF-Token` con el valor de la cookie `csrf_token`; los formularios
de la interfaz lo hacen automáticamente. Con `curl`, usa `-c cookies.txt` al
iniciar sesión y `-b cookies.txt` en las llamadas siguientes.

## Endpoints de la API

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/login` | público | Valida credenciales y entrega JWT + cookies |
| POST | `/api/v1/auth/register` | admin (o público si no hay cuentas) | Alta de usuarios |
| GET | `/api/v1/auth/me` | autenticado | Datos de la cuenta actual |
| POST | `/api/v1/auth/logout` | autenticado | Registra el cierre y borra la cookie |
| GET | `/api/v1/auth/roles` | admin | Catálogo de roles |
| POST | `/api/v1/auth/recuperar` | público | Envía (o registra) el enlace de recuperación |
| POST | `/api/v1/auth/restablecer` | público | Cambia la contraseña con el token del enlace |
| POST | `/api/v1/rag/chat` | autenticado | Pregunta al asistente (contrato final) |
| GET | `/api/v1/rag/estado` | autenticado | Disponibilidad del motor RAG |
| GET | `/salud` | público | Estado de las bases de datos |
| GET | `/docs` | público | Documentación interactiva |

Reglas de autenticación:

- El JWT expira a los `JWT_EXPIRACION_MINUTOS` (30 por defecto). Ese plazo
  implementa el cierre de sesión por inactividad (RF-01.3).
- El token incluye el rol; cada ruta decide el permiso (`admin` / `ventas`).
- La cuenta se relee de la base en cada petición: desactivar un usuario
  invalida sus tokens de inmediato.
- El asistente responde hoy con un aviso de motor provisional; el contrato
  (`respuesta`, `productos`, `aviso`, `modelo`) no cambia cuando llegue el RAG.

### Conectar pgAdmin a PostgreSQL

pgAdmin corre en otro contenedor, por lo que **no** debe usarse `localhost`
como host:

1. Abre http://localhost:8080 e inicia sesión.
2. Clic derecho en **Servers → Register → Server…**
3. **General** → Name: `Ferreteria`.
4. **Connection**:
   - Host: `db`
   - Port: `5432`
   - Maintenance database: `ferreteria`
   - Username / Password: los de `.env`
5. Guarda y despliega `ferreteria_rag` o `ferreteria_usuarios`.

Para ver el MER: clic derecho sobre una base → **ERD For Database**.

## Bases de datos

El esquema se define en `init.sql` y crea dos bases:

| Base | Tablas | Uso |
|---|---|---|
| `ferreteria_rag` | `archivos_subidos`, `proveedores`, `categoria`, `productos` | Catálogo e insumos del motor RAG (incluye `descripcion_vectorial vector(1536)` e índice HNSW) |
| `ferreteria_usuarios` | `rol`, `usuarios`, `bitacora` | Autenticación, roles y auditoría inmutable |
| `ferreteria` | — | Base de mantenimiento (la usa pgAdmin para conectarse) |

### Dos roles de base de datos

| Rol | Uso | Privilegios |
|---|---|---|
| `admin_ferreteria` | Administración y tareas puntuales | Superusuario |
| `app_ferreteria` | **La API** | Solo datos: `SELECT/INSERT/UPDATE/DELETE` en el catálogo, `SELECT/INSERT` en la bitácora. Sin `CREATE`, sin `DELETE` de usuarios, sin acceso a la estructura |

La contraseña de `app_ferreteria` se define en `APP_DB_PASSWORD` (`.env`) y
`init.sql` la aplica al crear el volumen. La API nunca usa la cuenta de
superusuario.

### Recrear el esquema

`init.sql` solo se ejecuta cuando el volumen `postgres_data` se crea por
primera vez. Para volver a aplicarlo:

```bash
docker compose down -v   # ¡elimina todos los datos!
docker compose up -d
```

Si ya tienes datos y solo falta la tabla de la Adenda 1, aplica la migración
idempotente sin borrar nada:

```bash
docker compose exec -T db psql -U postgres -d ferreteria_usuarios \
  < scripts/migracion_2_5.sql
```

## Pruebas

```bash
pytest -q
```

| Carpeta | Contenido |
|---|---|
| `unit/` | Caja blanca: esquema SQL, hashing, JWT, tokens de recuperación, pool |
| `integration/` | Caja negra: login, registro, roles, auditoría, páginas web |
| `boundary/` | Valores límite: expiración exacta del JWT |
| `security/` | Inyección SQL, permisos de BD, CSRF, endurecimiento de Docker |
| `stress/` | Carga masiva de catálogos (Semana 3) |

Resultado actual:

```text
329 passed
```

Las pruebas de integración **no tocan las bases de desarrollo**: al iniciar la
sesión clonan `ferreteria_rag` y `ferreteria_usuarios` como
`ferreteria_rag_test` y `ferreteria_usuarios_test`, y las eliminan al terminar.
Si PostgreSQL no responde, esas pruebas se omiten en lugar de fallar.

> Si pgAdmin tiene sesiones abiertas sobre las bases, PostgreSQL no permite
> clonarlas. En ese caso cierra las pestañas de consulta en pgAdmin y vuelve a
> ejecutar las pruebas.

## Estructura del proyecto

```text
app/                Código del backend (FastAPI)
  api/v1/           Rutas REST (/api/v1/...) y páginas HTML
  core/             Seguridad, JWT, sesión por cookie y auditoría
  db/               Pools de conexión a PostgreSQL
  models/           Acceso a datos (SQL parametrizado)
  schemas/          DTOs de Pydantic
  services/         Correo, recuperación, ETL, embeddings, búsqueda y LLM
  static/           CSS, JS, imágenes y Bootstrap servido localmente
templates/          Vistas Jinja2
tests/              Suite de pruebas
scripts/            Migraciones incrementales (sin borrar datos)
init.sql            Esquema de las dos bases
docker-compose.yml  PostgreSQL + pgAdmin + API
Dockerfile          Imagen de la API (usuario sin privilegios)
DESIGN.md           Sistema de diseño de la interfaz
PRODUCT.md          Verdad de producto para el diseño
docs/actas/         Actas de entrega semanales
```

## Seguridad aplicada

- Contraseñas **fuera del repositorio** (`.env` ignorado por Git).
- Contraseñas con **scrypt** (16 MiB de costo por verificación) y sal aleatoria;
  nunca se guardan ni se registran en claro.
- JWT firmado con **HS256** y secreto de 48 bytes; sin secreto válido la
  aplicación no arranca.
- **Consultas parametrizadas** en todo el acceso a datos (anti-SQL Injection).
- Validación estricta de entrada con Pydantic (`extra="forbid"`).
- Rol de base de datos de **mínimo privilegio** para la API.
- Bitácora **inmutable**: solo `INSERT` y `SELECT`; los triggers bloquean
  `UPDATE`, `DELETE` y `TRUNCATE` incluso para el propietario.
- Puertos publicados solo en `127.0.0.1` (cambia `BIND_ADDRESS` para un VPS).
- `no-new-privileges` en los tres contenedores e imágenes con versión fija.
- La imagen de la API corre como `uid 10001` con el sistema de archivos en solo
  lectura y `/tmp` en memoria; no incluye `.env` ni credenciales.
- JWT en cookie `HttpOnly` + `SameSite=Lax`, con CSRF de doble envío y
  validación de `Origin` en las peticiones que cambian datos.
- Enlace de recuperación de un solo uso, con huella SHA-256 y caducidad de 30
  minutos; la respuesta es la misma exista o no la cuenta.

## Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| pgAdmin no conecta con host `localhost` | Usa `db` (nombre del servicio) |
| Solo aparece la base `ferreteria` | El volumen es antiguo: `docker compose down -v && docker compose up -d` |
| Cambios en `init.sql` no se aplican | El script solo corre con volumen nuevo |
| `Configuracion invalida: Falta JWT_SECRET` | Copia `.env.example` a `.env` y define los valores |
| `password authentication failed for user "app_ferreteria"` | Recrea el volumen para que `init.sql` aplique `APP_DB_PASSWORD` |
| Las pruebas de integración se omiten | PostgreSQL apagado o pgAdmin con sesiones abiertas sobre las bases |
| `403` al enviar un formulario | Falta el encabezado `X-CSRF-Token` o el origen no coincide con `URL_BASE` |
| No llega el correo de recuperación | Sin SMTP configurado: busca el enlace en el log de Uvicorn |
| `docker: command not found` en WSL | Activa la integración WSL 2 en Docker Desktop o usa PowerShell |
| Puerto 5432/8000/8080 ocupado | Cambia `POSTGRES_HOST_PORT` / `API_HOST_PORT` / `PGADMIN_HOST_PORT` en `.env` |
| La API en Docker no arranca: puerto 8000 en uso | Detén `uvicorn` o define otro `API_HOST_PORT`; recuerda ajustar `URL_BASE` |

## Documentación del proyecto

- `prompts/requisitos_funcionales_y_no_funcionales_del_sistema.md`
- `prompts/lista_de_tareas_y_checklist_de_ejecucion_del_proyecto.md`
- `prompts/estructura_y_arquitectura_del_proyecto.md`
- `DESIGN.md` — sistema de diseño (colores, tipografía, componentes)
- `docs/actas/` — actas de entrega

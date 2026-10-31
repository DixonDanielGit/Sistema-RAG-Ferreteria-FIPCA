# Sistema Web de Gestión de Inventario e IA RAG

Aplicación web para **FERRE-INVERSIONES PEREZ C.A.** que combina gestión de
inventario con un asistente basado en RAG (Retrieval-Augmented Generation)
sobre el catálogo real de productos.

- **Backend:** Python 3.11+ / FastAPI / Uvicorn / Pydantic
- **Base de datos:** PostgreSQL 16 + `pgvector`
- **Frontend:** Jinja2 + Bootstrap 5 + JavaScript vanilla (fetch/AJAX)
- **Interfaz:** SweetAlert2 global y DataTables Responsive en tablas; recursos
  locales en `app/static/vendor/` sin dependencia de CDN
- **IA:** embeddings locales (Semana 4) + modelo generativo (Semana 5)
- **Infraestructura:** Docker + Docker Compose

> Estado actual: **Semana 3 completada; implementación técnica de Semana 4 lista
> para piloto** — incluye embeddings locales y búsqueda vectorial. Falta validar
> relevancia y latencia con una muestra del catálogo de desarrollo. El chat sigue
> provisional hasta la integración RAG de Semana 5.

Las versiones fuente de las dependencias JavaScript se fijan en `package.json`.
Los archivos de distribución y sus licencias están incluidos en
`app/static/vendor/`, por lo que ejecutar la interfaz no requiere Node.js ni
conexión a un CDN. Se incluyen jQuery 3.7.1, DataTables 2.3.4, Responsive
3.0.7 y SweetAlert2 11.26.25.

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
| Imagen | `ferreteria-api:4.0` (Python 3.12 slim) |
| Contenedor | `api_ferreteria`, usuario sin privilegios `uid 10001` |
| Puerto | `API_HOST_PORT` de `.env` (8000 por defecto), solo en `BIND_ADDRESS` |
| Origen público | `URL_BASE` de `.env`, debe coincidir con la barra del navegador |
| Salud | `healthcheck` sobre `/salud` cada 30 s |
| Disco | Solo lectura (`read_only`); `/tmp` en memoria, originales en `/app/uploads` y modelo en `/app/model-cache` persistentes |

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
administrador o una cuenta con la capacidad `usuarios:gestionar` puede
administrar cuentas. Solo el administrador puede asignar el rol protegido
`admin`.

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

**Panel de fuentes.** El administrador puede cargar lotes de hasta 20 archivos
PDF, XLSX, DOCX o TXT (máximo 20 MB cada uno). Cada archivo se valida de forma
independiente; un archivo rechazado no detiene los demás. El panel muestra el
resultado y el historial de las últimas 100 cargas. Ventas puede consultar el
historial, pero no cargar catálogos. Los originales se guardan bajo un nombre
UUID en `UPLOADS_DIR` (un volumen persistente `/app/uploads` en Docker), nunca
en los estáticos. PDF/XLSX/DOCX necesitan columnas reconocibles de código,
nombre y precio; TXT también admite el orden posicional documentado
`codigo;nombre;precio;descripcion;marca`. El ETL no admite CSV ni XLS.

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
| POST | `/api/v1/auth/register` | `usuarios:gestionar` (o público si no hay cuentas) | Alta de usuarios |
| GET | `/api/v1/auth/me` | autenticado | Datos de la cuenta actual |
| PUT | `/api/v1/auth/me` | autenticado | Actualiza nombre, apellido, usuario, correo y cédula propios |
| GET | `/api/v1/auth/me/imagen` | autenticado | Obtiene la imagen de perfil propia |
| POST / DELETE | `/api/v1/auth/me/imagen` | autenticado | Guarda o quita la imagen propia |
| GET | `/api/v1/auth/usuarios` | `usuarios:gestionar` | Lista cuentas sin hashes ni imágenes |
| PUT | `/api/v1/auth/usuarios/{id}` | `usuarios:gestionar` | Actualiza cuenta y rol |
| PATCH | `/api/v1/auth/usuarios/{id}/rol` | `usuarios:gestionar` | Cambia el rol de una cuenta |
| PATCH | `/api/v1/auth/usuarios/{id}/estado` | `usuarios:gestionar` | Activa o desactiva una cuenta |
| GET | `/api/v1/auth/configuracion/admin` | `configuracion:diagnostico` | Consulta estado de bases y límites técnicos |
| POST | `/api/v1/auth/logout` | autenticado | Registra el cierre y borra la cookie |
| GET | `/api/v1/auth/roles` | `usuarios:gestionar` | Catálogo de roles para asignarlos a cuentas |
| GET | `/api/v1/auth/roles/permisos` | admin | Catálogo fijo de capacidades |
| POST / PUT / DELETE | `/api/v1/auth/roles[/{id}]` | admin | Administra roles y sus capacidades |
| POST | `/api/v1/auth/recuperar` | público | Envía (o registra) el enlace de recuperación |
| POST | `/api/v1/auth/restablecer` | público | Cambia la contraseña con el token del enlace |
| POST | `/api/v1/inventario/ingesta` | `catalogos:ingestar` | Procesa un lote de catálogos |
| GET | `/api/v1/inventario/archivos` | autenticado | Historial de las últimas 100 cargas |
| DELETE | `/api/v1/inventario/archivos/{id}` | `catalogos:eliminar` | Elimina un catálogo y sus productos |
| POST | `/api/v1/rag/chat` | autenticado | Pregunta al asistente (contrato final) |
| GET | `/api/v1/rag/estado` | autenticado | Disponibilidad del motor RAG |
| GET | `/salud` | público | Estado de las bases de datos |
| GET | `/docs` | público | Documentación interactiva |

Reglas de autenticación:

- El JWT expira a los `JWT_EXPIRACION_MINUTOS` (30 por defecto). Ese plazo
  implementa el cierre de sesión por inactividad (RF-01.3).
- El token incluye el rol; la cuenta y sus capacidades vigentes se releen de la
  base en cada petición. Un cambio o revocación de permisos tiene efecto sin
  renovar el JWT, y desactivar una cuenta invalida sus tokens de inmediato.
- Solo `admin` puede crear, editar o eliminar roles y capacidades. `admin` está
  protegido y conserva acceso total; los roles asignados a cuentas no se
  pueden eliminar. Las capacidades se seleccionan de una lista fija del
  sistema, no son permisos CRUD arbitrarios.
- Las pantallas `/usuarios`, `/perfil` y `/configuracion` muestran funciones
  según las capacidades. Las cuentas se desactivan en vez de borrarse; el
  último administrador activo no puede desactivarse ni perder su rol.
- La foto de perfil se almacena como WebP normalizado en `BYTEA`; se reciben
  JPEG, PNG o WebP de hasta 2 MB. Sin foto se muestra el avatar local.
- El asistente responde hoy con un aviso de motor provisional; el contrato
  (`respuesta`, `fuentes`, `aviso`, `modelo`) no cambia cuando llegue el RAG.

La carga acepta un campo multipart repetido `archivos`. Para probarla desde
terminal con un token Bearer:

```bash
curl -X POST http://localhost:8000/api/v1/inventario/ingesta \
  -H "Authorization: Bearer <token>" \
  -F "archivos=@catalogo.txt"
```

Los `.xlsx` y `.docx` se revisan además contra paquetes ZIP dañados o con
relaciones de compresión anómalas. Cada archivo se limita a 20 000 filas y los
PDF a 300 páginas. Los productos se actualizan por código; el proceso conserva
el stock existente y fija el IVA en 16 %.

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
| `ferreteria_rag` | `archivos_subidos`, `proveedores`, `categoria`, `productos` | Catálogo e insumos del motor RAG (incluye `descripcion_vectorial vector(384)` e índice HNSW) |
| `ferreteria_usuarios` | `rol`, `permiso`, `rol_permiso`, `usuarios`, `tokens_recuperacion`, `bitacora` | Autenticación, capacidades, perfiles y auditoría inmutable |
| `ferreteria` | — | Base de mantenimiento (la usa pgAdmin para conectarse) |

### Dos roles de base de datos

| Rol | Uso | Privilegios |
|---|---|---|
| `admin_ferreteria` | Administración y tareas puntuales | Superusuario |
| `app_ferreteria` | **La API** | Solo datos: catálogo, cuentas y roles; catálogo de capacidades de solo lectura; `SELECT/INSERT` en la bitácora. Sin `CREATE`, sin `DELETE` de usuarios, sin acceso a la estructura |

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

Si ya tienes datos, aplica las migraciones idempotentes sin borrar nada. La
migración `3_0` agrega los metadatos de ingesta y `4_0` prepara los vectores
para el modelo local. La migración `4_0` conserva el catálogo y solo permite el
cambio de dimensión si los vectores existentes están vacíos; si encuentra
embeddings previos, aborta sin convertirlos:

```bash
venv\Scripts\python.exe scripts\aplicar_migracion.py 2_5
venv\Scripts\python.exe scripts\aplicar_migracion.py 3_0
venv\Scripts\python.exe scripts\aplicar_migracion.py 4_0
venv\Scripts\python.exe scripts\aplicar_migracion.py 5_0
venv\Scripts\python.exe scripts\aplicar_migracion.py 6_0
```

La migración `5_0` agrega la imagen de perfil y protege la unicidad sin
distinguir mayúsculas; se ejecuta en `ferreteria_usuarios` y conserva los datos.
Debe aplicarse antes de desplegar una versión que use las vistas de cuenta.

La migración `6_0` agrega el catálogo cerrado `permiso`, la relación
`rol_permiso` y protección del rol `admin`. Asigna todas las capacidades
vigentes al rol `admin` y es seguro volver a ejecutarla para completar esas
asignaciones si una ejecución anterior dejó la relación vacía. Conserva
usuarios y roles existentes; aplíquela antes de arrancar la API de esta versión.

### Piloto local de embeddings (Semana 4)

El piloto usa `intfloat/multilingual-e5-small`, un modelo multilingüe gratuito
que se ejecuta localmente y genera vectores de 384 dimensiones. La primera
ejecución descarga los pesos públicos del modelo; el contenido del catálogo no
se envía a un proveedor externo. En Docker, los pesos permanecen en el volumen
`model_cache` y la inferencia corre en la imagen Python 3.12. FastEmbed/ONNX
Runtime no tiene rueda para el Python 3.15 usado por el entorno virtual de
desarrollo; use Docker o un entorno local Python 3.12 para este comando.

Después de aplicar `4_0`, reconstruye la imagen si aún no tiene FastEmbed y
vectoriza primero una muestra pequeña:

```powershell
docker compose up -d --build api
docker compose exec api python scripts\vectorizar_catalogo.py --lote 10
docker compose exec api python scripts\buscar_productos_vectorial.py "taladro para concreto"
```

La orden de vectorización solo se ejecuta cuando se la invoca. Comprueba los
resultados antes de procesar el catálogo completo con `--todos`. Para revisar
el estado desde pgAdmin:

```sql
SELECT COUNT(*) AS productos,
       COUNT(*) FILTER (WHERE descripcion_vectorial IS NOT NULL) AS vectorizados
FROM productos;
```

La búsqueda semántica todavía es un servicio de backend de Semana 4; el chat web
seguirá mostrando su respuesta provisional hasta la integración RAG de Semana 5.
La reingesta invalida el vector cuando cambia nombre, marca o descripción para
que el siguiente proceso de vectorización lo regenere.

**Smoke test técnico (dataset sintético):** el modelo devolvió 384 dimensiones.
En cuatro consultas de ejemplo, el producto esperado quedó primero en 3 de 4;
la consulta de brocas priorizó un taladro relacionado. Con los pesos ya
descargados, cargar el modelo y vectorizar cuatro pasajes tomó 16,0 s; codificar
las cuatro consultas con el modelo cargado tomó 162,5 ms. Esto es una comprobación
preliminar, no una medición de búsqueda PostgreSQL ni una garantía de calidad
para el catálogo real. Revise el [registro preliminar de Semana 4](docs/actas/acta_04_embeddings_busqueda.md)
antes de procesar el catálogo completo.

## Pruebas

```bash
venv\Scripts\python.exe -m pytest tests/ -q
```

| Carpeta | Contenido |
|---|---|
| `unit/` | Caja blanca: esquema SQL, hashing, JWT, ETL, tokens y pool |
| `integration/` | Caja negra: login, registro, roles, auditoría y páginas web |
| `boundary/` | Valores límite: expiración exacta del JWT |
| `security/` | Inyección SQL, permisos de BD, CSRF, endurecimiento de Docker |
| `stress/` | Lote real de 20 archivos / 5000 productos (Semana 3, optativo) |

```text
Última verificación: **378 pruebas pasaron y 1 se omitió** en 200,83 s. La
prueba optativa de estrés ETL también pasó: 20 archivos y 5000 productos dentro
del objetivo de 4,25 s.
```

Las pruebas de integración **no tocan las bases de desarrollo**: al iniciar la
sesión clonan `ferreteria_rag` y `ferreteria_usuarios` como
`ferreteria_rag_test` y `ferreteria_usuarios_test`, y las eliminan al terminar.
La copia de prueba recibe automáticamente las migraciones ETL, vectorial y de
perfil de usuario; la
base de desarrollo no se altera. Si PostgreSQL no responde, esas pruebas se
omiten en lugar de fallar.

La prueba de carga reducida es optativa:

```powershell
$env:PRUEBA_ESTRES = "1"
venv\Scripts\python.exe -m pytest tests\stress -q -s
```

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

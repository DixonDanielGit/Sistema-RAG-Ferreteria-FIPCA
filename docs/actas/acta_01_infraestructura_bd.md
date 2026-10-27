# Acta 1 — Inicio del Proyecto e Infraestructura de Datos

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario con Inteligencia Artificial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Semana 1 |
| **Fecha de entrega** | 27 de octubre de 2026 |
| **Estado** | Entregado y verificado |

---

## 1. Resumen para la gerencia

Durante esta primera semana se construyó **la base sobre la cual funcionará todo
el sistema**: el lugar donde se guardará la información de la empresa y el
entorno donde se ejecutará la aplicación.

No se trata de una maqueta ni de una demostración. Es la infraestructura real
que se usará en producción, ya instalada, configurada y probada.

**En palabras sencillas:**

- Se preparó un **almacén digital** para el inventario y los usuarios.
- Ese almacén ya tiene las **reglas del negocio incorporadas**: el IVA no puede
  ser distinto de 16 %, un precio no puede ser negativo, un código de producto
  no puede repetirse.
- Se activó un **registro de auditoría que nadie puede alterar**: todo lo que
  ocurra en el sistema queda anotado y no se puede borrar ni modificar, ni
  siquiera por error.
- Se habilitó la tecnología que permitirá al asistente de IA **entender y
  buscar productos por su descripción**, no solo por coincidencia exacta de
  texto.

**Resultado de la verificación:** se ejecutaron **37 controles automáticos** y
todos resultaron conformes. Un control adicional quedó pendiente por diseño,
ya que corresponde a una etapa posterior del proyecto.

**Inversión de tiempo:** una semana, conforme al cronograma aprobado.

---

## 2. Qué se construyó y para qué sirve

### 2.1 El almacén de información

La información se organizó en **dos depósitos separados**, tal como establece
el diagrama de datos del proyecto. Esta separación es una medida de seguridad:
si alguien accediera al catálogo de productos, no tendría acceso a las cuentas
de usuario, y viceversa.

**Depósito A — Catálogo e inventario**

| Qué guarda | Utilidad para el negocio |
|---|---|
| Productos | El inventario completo: código, nombre, marca, precio, existencia |
| Categorías | Agrupa los productos para búsquedas y reportes |
| Proveedores | A quién se le compra cada producto |
| Archivos cargados | Los catálogos que se importen (Excel, PDF, etc.) y su trazabilidad |

Cada producto guarda además una **"huella digital" de su descripción**. Esa
huella es lo que permitirá que el asistente de IA responda preguntas como
*"¿tienen tornillos para madera?"* aunque el producto esté registrado como
*"tornillo autorroscante 3 pulgadas"*.

**Depósito B — Usuarios y auditoría**

| Qué guarda | Utilidad para el negocio |
|---|---|
| Roles | Los dos perfiles definidos: **administrador** y **ventas** |
| Usuarios | Las cuentas del personal, con su rol asignado |
| Bitácora | El registro de todo lo que ocurre en el sistema |

Los dos roles ya están creados:

- **Administrador:** control total — inventario, usuarios, carga de catálogos y
  consulta de la bitácora.
- **Ventas:** consulta de productos, disponibilidad y uso del asistente de IA.

### 2.2 Las reglas del negocio ya están protegidas

Un aspecto central de esta semana: las reglas no dependen de que el programador
las recuerde, están **grabadas en el propio almacén**. Aunque en el futuro se
cometa un error en el sistema, la información no se corrompe.

| Regla del negocio | Cómo queda protegida |
|---|---|
| El IVA es 16 % y no se negocia | El sistema **rechaza** cualquier otro valor |
| Ningún producto tiene precio negativo | El sistema **rechaza** precios menores a cero |
| No se puede vender lo que no existe | La existencia **no puede ser negativa** |
| Dos productos no pueden tener el mismo código | El sistema **rechaza** códigos duplicados |
| La auditoría es inviolable | El registro **no admite borrado ni modificación** |

Sobre el último punto conviene ser explícito: la bitácora **no se puede
alterar ni eliminar**, ni por el administrador del sistema. Si se intenta, la
operación falla. Esto es lo que da valor legal y operativo al registro.

### 2.3 Decisiones tomadas con la empresa

**Sobre la alerta de bajo inventario.** El diseño original contemplaba un
campo de "existencia mínima" por cada producto. A solicitud del cliente se
eliminó: se consideró redundante. En su lugar, el sistema usará **un único
umbral general configurable** para toda la empresa. Es más simple de mantener y
evita tener que ajustar producto por producto.

**Sobre la separación de datos.** Se optó por dos depósitos independientes en
lugar de uno solo. Implica un poco más de trabajo técnico, pero ofrece una
barrera de seguridad real entre el inventario y las cuentas de acceso.

---

## 3. Cómo se comprobó que funciona

### 3.1 Controles automáticos

En lugar de revisar a mano, se escribieron **programas de verificación** que
comprueban el sistema cada vez que se modifica. Son 37 controles agrupados en
tres áreas:

| Área | Controles | Qué comprueban |
|---|---|---|
| Estructura de la información | 20 | Que existan los dos depósitos, las tablas, las reglas del IVA, precios, existencias, códigos y la inviolabilidad de la auditoría |
| Seguridad del almacén | 8 | Que no se pueda entrar sin contraseña, que no haya accesos indebidos y que la auditoría esté realmente protegida |
| Seguridad de la instalación | 10 | Que el servidor no quede expuesto a internet y que las contraseñas no estén escritas en el código |

**Resultado:**

```text
37 controles aprobados
 1 control omitido (corresponde a una etapa posterior del proyecto)
 0 controles fallidos
```

Estos controles se vuelven a ejecutar en cada etapa siguiente. Si un cambio
futuro rompiera una regla del negocio, el sistema lo detecta **antes** de que
llegue a producción.

### 3.2 Verificación de la instalación en vivo

| Verificación | Resultado |
|---|---|
| Servicio de base de datos en ejecución | ✅ Operativo y estable |
| Panel de administración web (pgAdmin) | ✅ Operativo y accesible |
| Almacén responde a consultas | ✅ Confirmado |
| Reglas del negocio activas | ✅ Confirmado (IVA, precios, códigos) |
| Auditoría protegida contra alteración | ✅ Confirmado (probado con intentos de borrado y modificación) |

---

## 4. Seguridad

La información de la empresa es el activo más valioso del sistema. Las medidas
aplicadas en esta etapa:

| Medida | Qué significa |
|---|---|
| Contraseñas fuera del código fuente | Aunque alguien obtenga el código, no obtiene las claves |
| Acceso restringido al equipo local | El sistema **no es visible desde internet** en esta etapa |
| Servicios sin privilegios elevados | Si un servicio fuera comprometido, el daño queda contenido |
| Versiones fijas del software | La instalación es reproducible: no cambia sola de un día para otro |
| Acceso con contraseña obligatoria | No se puede entrar al almacén sin credenciales |
| Un solo administrador técnico | Se reduce al mínimo la cantidad de cuentas con control total |
| Auditoría inviolable | El registro de operaciones no se puede alterar |

**Limitación conocida y aceptada:** dentro del propio servidor, las conexiones
locales internas usan un mecanismo de confianza simplificado. Es el
comportamiento estándar del software de base de datos y **no es accesible desde
fuera del servidor**.

**Mejora prevista para la próxima semana:** crear una cuenta de aplicación con
permisos limitados, para que el sistema no opere con la cuenta de
administrador total.

---

## 5. Entregables de esta semana

| Entregable | Qué es | Dónde está |
|---|---|---|
| Estructura de la información | Definición completa del almacén y sus reglas | `init.sql` |
| Instalación automatizada | Permite levantar todo el sistema con un comando | `docker-compose.yml` |
| Configuración protegida | Claves separadas del código | `.env` / `.env.example` |
| Programas de verificación | Los 37 controles automáticos | `tests/` |
| Manual de operación | Instrucciones de arranque y uso | `README.md` |
| Este informe | Documento de entrega | `docs/actas/` |

---

## 6. Lo que viene

| Etapa | Contenido | Valor para la empresa |
|---|---|---|
| Semana 2 | Acceso al sistema con usuario y contraseña | Cada empleado entra con su propia cuenta |
| Semana 3 | Carga de catálogos desde Excel y otros formatos | Se deja de digitar el inventario a mano |
| Semana 4 | Búsqueda inteligente por descripción | El asistente entiende el lenguaje del cliente |
| Semana 5 | Asistente de IA para consultas | Respuestas en lenguaje natural sobre el inventario real |
| Semanas 6–8 | Pantallas, reportes, pruebas finales y puesta en marcha | Sistema listo para operar |

---

## 7. Recomendaciones

1. **Definir las cuentas de usuario reales** antes de la Semana 2: nombres del
   personal y qué rol le corresponde a cada uno.
2. **Reunir los catálogos de proveedores** en formato digital (Excel o PDF)
   para aprovechar la carga masiva de la Semana 3.
3. **Decidir el umbral general de bajo inventario**: cuántas unidades de un
   producto se consideran "poco stock" para toda la empresa.
4. **Definir el responsable de revisar la bitácora**: la auditoría solo aporta
   valor si alguien la consulta periódicamente.

---

## 8. Conformidad

El suscrito declara haber ejecutado y verificado los trabajos descritos en este
informe, correspondientes a la Semana 1 del cronograma aprobado.

| Rol | Nombre | Firma | Fecha |
|---|---|---|---|
| Desarrollador | Dixon Daniel Bastias Hernandez | | |
| Representante de la empresa | | | |

---

## Anexo técnico

*Esta sección está dirigida al personal técnico. No es necesaria para la
comprensión del informe.*

### A.1 Componentes instalados

| Componente | Versión / valor |
|---|---|
| Motor de base de datos | PostgreSQL 16.15 |
| Extensión de búsqueda vectorial | `pgvector` 0.8.7 |
| Extensión de búsqueda por texto | `pg_trgm` 1.6 |
| Panel de administración | pgAdmin 4 versión 9.18 |
| Contenedor de base de datos | `pgvector/pgvector:0.8.7-pg16` |
| Contenedor de administración | `dpage/pgadmin4:9.18` |
| Puerto de base de datos | `127.0.0.1:5432` |
| Puerto de pgAdmin | `127.0.0.1:8080` |

### A.2 Estructura de datos

**Base `ferreteria_rag`**

| Tabla | Claves y restricciones |
|---|---|
| `archivos_subidos` | PK `id_archivo` |
| `proveedores` | PK `id_proveedores` |
| `categoria` | PK `id_categoria`, `nombre` único |
| `productos` | PK `id`, `codigo` único, `iva` fijo 16 %, `precio`/`stock`/`descuentos` ≥ 0, `descripcion_vectorial vector(1536)` |

Índices: HNSW sobre `descripcion_vectorial` (`vector_cosine_ops`) y GIN trigram
sobre `nombre`, `marca` y `descripcion`.

**Base `ferreteria_usuarios`**

| Tabla | Claves y restricciones |
|---|---|
| `rol` | PK `id_rol`, `nombre` único; semilla `admin`, `ventas` |
| `usuarios` | PK `id`, cédula/usuario/correo únicos, FK a `rol` (`RESTRICT`), `activo` |
| `bitacora` | PK `id_bitacora`, FK a `usuarios` (`RESTRICT`), `ip`, `modulo`; `id_usuario` nullable para logins fallidos |

Inmutabilidad: `trg_bitacora_inmutable` bloquea `UPDATE` y `DELETE`;
`trg_bitacora_no_truncate` bloquea `TRUNCATE`. La FK `ON DELETE RESTRICT`
impide eliminar un usuario que tenga historial de auditoría.

**Base `ferreteria`** — base de mantenimiento, requerida por pgAdmin para
conectarse. No contiene tablas de la aplicación.

### A.3 Ejecución de la suite de pruebas

```bash
# Windows (entorno virtual del proyecto)
venv\Scripts\python.exe -m pytest tests/ -q

# Suites por separado
pytest tests/unit -q       # estructura de datos (20)
pytest tests/security -q   # seguridad (18)

# Una prueba específica, con detalle
pytest tests/unit/test_init_db.py::test_iva_distinto_de_16_es_rechazado -v
```

Comportamiento:

- Las pruebas de `tests/unit/` y `tests/security/test_db_seguridad.py`
  requieren el contenedor en ejecución. Cada prueba abre una transacción y
  hace `rollback`, por lo que no deja datos residuales.
- Si PostgreSQL no está disponible, esas pruebas se **omiten** (`skip`) en
  lugar de fallar, mediante `pytest.skip` con el motivo del error de conexión.
- `tests/security/test_compose_hardening.py` es estático: analiza
  `docker-compose.yml` y `.dockerignore` con expresiones regulares, sin
  necesidad de Docker ni de base de datos.

Resultado de la última ejecución:

```text
37 passed, 1 skipped in 62.14s
```

La única prueba omitida es `test_dockerfile_no_copia_secretos`, que aplica a
partir de la Semana 8, cuando exista el `Dockerfile` de la aplicación.

### A.4 Cobertura de las pruebas

**`tests/unit/test_init_db.py` (20 casos):** existencia de las dos bases;
tablas presentes en cada una; ausencia de tablas cruzadas; extensión `vector`
en la base RAG; índice HNSW; columnas del SRS en `productos`; columna `activo`
en `usuarios`; filtros `ip`/`modulo` en `bitacora`; semilla de roles; valores
por defecto (IVA 16.00, descuentos 0.00, stock 0); rechazo de IVA distinto de
16 %; rechazo de precio negativo; rechazo de stock negativo; unicidad de
`codigo`; `id_usuario` nulo en login fallido; rechazo de `UPDATE`, `DELETE` y
`TRUNCATE` sobre `bitacora`; conservación de la auditoría al intentar eliminar
un usuario.

**`tests/security/test_db_seguridad.py` (8 casos):** un solo superusuario;
`pg_hba` sin `trust` en conexiones TCP externas; conexión sin contraseña
rechazada; contraseña incorrecta rechazada; `PUBLIC` sin `CREATE` sobre el
esquema; sin concesiones a `PUBLIC` sobre las tablas; `vector` solo en la base
RAG; sin acceso de otros roles a `bitacora`.

**`tests/security/test_compose_hardening.py` (10 casos):** imágenes con versión
numérica fija; puertos solo en loopback; `no-new-privileges` en ambos
servicios; ningún contenedor privilegiado; `init.sql` en solo lectura; ausencia
de la clave `version` obsoleta; contraseñas provenientes de `.env`; healthchecks
definidos; `.dockerignore` excluye secretos; `Dockerfile` no copia `.env`.

### A.5 Estado de los contenedores

```text
NAME                  IMAGE                          STATUS        PORTS
pgadmin_ferreteria    dpage/pgadmin4:9.18            Up (healthy)  127.0.0.1:8080->8080/tcp
postgres_ferreteria   pgvector/pgvector:0.8.7-pg16   Up (healthy)  127.0.0.1:5432->5432/tcp
```

### A.6 Reproducción del entorno

`init.sql` se monta en `/docker-entrypoint-initdb.d/` y se ejecuta **solo
cuando el volumen `postgres_data` se crea por primera vez**. Cualquier cambio de
esquema exige recrear el volumen:

```bash
docker compose down -v   # elimina todos los datos
docker compose up -d
```

pgAdmin no persiste su registro de servidores: al recrear el contenedor debe
registrarse de nuevo con host `db`, puerto `5432` y base de mantenimiento
`ferreteria`.

### A.7 Diagramas de base de datos

Generar en pgAdmin con **clic derecho sobre la base → ERD For Database** y
exportar con **Download image**:

- `mer_ferreteria_rag.png`
- `mer_ferreteria_usuarios.png`

### A.8 Riesgos técnicos identificados

| Riesgo | Impacto | Mitigación |
|---|---|---|
| `trust` en conexiones locales internas | Bajo: no alcanzable desde fuera del contenedor | Riesgo aceptado; propio de la imagen oficial |
| Sin rol de aplicación dedicado | Medio: la app usaría el superusuario | Se corrige en Semana 2 con dos DSN de mínimo privilegio |
| `descripcion_vectorial` fija en 1536 dimensiones | Medio: condiciona el modelo de embeddings | El modelo de la Semana 4 debe respetar esa dimensión |
| pgAdmin sin volumen persistente | Bajo: solo molestia operativa | Documentado en el manual |
| Recrear el volumen borra los datos | Alto en producción | Aplicar solo en desarrollo; en producción usar migraciones |

---

*Documento generado como parte del entregable de la Semana 1.*

# Acta 2 — Seguridad de Acceso y Auditoría

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario con Inteligencia Artificial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Semana 2 |
| **Fecha de entrega** | 27 de octubre de 2026 |
| **Estado** | Entregado y verificado |

---

## 1. Resumen para la gerencia

Esta semana se habilitó **el acceso al sistema**: cada empleado entra con su
propia cuenta y contraseña, y el sistema sabe en todo momento quién hizo qué.

Hasta la semana pasada existía el almacén de datos, pero no había forma de
entrar. Ahora existe la puerta, la cerradura y el libro de registro.

**En palabras sencillas:**

- **Cada persona tiene su cuenta.** Se acabaron las claves compartidas: si
  alguien consulta un precio o modifica un producto, queda su nombre asociado.
- **Los permisos son distintos según el cargo.** Un vendedor consulta
  inventario; un administrador además gestiona usuarios y revisa la auditoría.
  Un vendedor no puede darse permisos a sí mismo.
- **La contraseña no se guarda en ningún lado.** El sistema almacena una
  "huella" matemática de la contraseña, de la cual no se puede volver atrás.
  Ni el desarrollador ni el dueño del sistema pueden leer las contraseñas.
- **La sesión se cierra sola.** Pasados 30 minutos sin actividad, el sistema
  exige volver a entrar. Si un empleado olvida cerrar sesión en una
  computadora, la sesión muere igual.
- **Todo queda registrado y nada se puede borrar.** Cada entrada al sistema
  (exitosa o fallida), cada alta de usuario y cada error queda anotado con
  fecha, hora, usuario, módulo e IP del equipo. Ese registro **no se puede
  alterar ni eliminar**, ni siquiera con la cuenta de administrador.

**Resultado de la verificación:** se ejecutaron **230 controles automáticos**
y todos resultaron conformes. Uno queda pendiente por diseño (corresponde a
una etapa posterior). Entre ellos, **42 controles intentan atacar el sistema**
con técnicas reales de inyección de código, y ninguno tuvo éxito.

**Inversión de tiempo:** una semana, conforme al cronograma aprobado.

---

## 2. Qué puede hacer cada rol

El sistema reconoce dos perfiles, definidos en los requisitos del proyecto:

| Acción | Administrador | Ventas |
|---|:---:|:---:|
| Entrar al sistema | ✅ | ✅ |
| Consultar productos y disponibilidad | ✅ | ✅ |
| Usar el asistente de IA (a partir de Semana 5) | ✅ | ✅ |
| Crear y modificar productos | ✅ | ❌ |
| Cargar catálogos de proveedores | ✅ | ❌ |
| Crear cuentas de usuario | ✅ | ❌ |
| Consultar la bitácora de auditoría | ✅ | ❌ |
| Desactivar cuentas | ✅ | ❌ |

Una cuenta **no se elimina**: se desactiva. Esa decisión es deliberada y
responde a una razón de control: si se pudiera borrar un usuario, se perdería
el rastro de lo que hizo. Al desactivarla, la persona no puede entrar pero su
historial permanece.

Desactivar una cuenta tiene efecto **inmediato**: aunque la persona tenga una
sesión abierta, en su siguiente acción el sistema la rechaza.

---

## 3. Cómo se protege una contraseña

Esta es la parte que más consultas genera, así que conviene explicarla.

Cuando un empleado define su contraseña, el sistema **no la guarda**. Le aplica
un procedimiento matemático de un solo sentido (llamado *scrypt*) y guarda el
resultado, que llamamos "huella". Ese procedimiento tiene tres propiedades:

1. **Es irreversible.** De la huella no se puede reconstruir la contraseña,
   ni con el código del sistema en la mano.
2. **Es distinta cada vez.** Dos personas con la misma contraseña producen
   huellas diferentes, así que nadie puede deducir que comparten clave.
3. **Es lento a propósito.** Verificar una contraseña tarda unas centésimas de
   segundo: imperceptible para el empleado, pero probar millones de
   combinaciones le tomaría años a un atacante.

**Consecuencia práctica:** si un empleado olvida su contraseña, **no se puede
recuperar**. El administrador debe asignarle una nueva. Esto es una garantía
de seguridad, no una limitación.

**Reglas mínimas de contraseña:** al menos 8 caracteres, combinando letras y
números, sin espacios al inicio ni al final, y un máximo de 128 caracteres.
La longitud es lo que realmente encarece un ataque, por eso no se imponen
reglas arbitrarias de mayúsculas y símbolos.

---

## 4. El libro de registro (bitácora de auditoría)

Cada vez que ocurre algo relevante, el sistema escribe una línea en la
bitácora. Es automático: **no depende de que el programa se acuerde de
anotarlo**, lo hace el propio sistema al interceptar cada petición.

### Qué se registra

| Evento | Ejemplo de registro |
|---|---|
| Entrada exitosa | *login exitoso (dperez)* |
| Contraseña incorrecta | *login fallido: contraseña incorrecta (dperez)* |
| Intento con usuario inexistente | *login fallido: identificador inexistente (xxxxx)* |
| Cuenta desactivada | *login rechazado: cuenta inactiva (dperez)* |
| Alta de usuario | *alta de usuario (vendedor2) con rol ventas* |
| Cierre de sesión | *cierre de sesión (dperez)* |
| Error del sistema | *GET /api/v1/inventario respondió 403* |

Cada línea guarda **fecha, hora, usuario, acción, módulo e IP** del equipo de
origen. Con eso se puede responder: *¿quién consultó el precio?, ¿desde qué
equipo?, ¿cuándo?, ¿cuántos intentos fallidos hubo?*

### Qué NO se puede hacer

| Intento | Resultado |
|---|---|
| Modificar una línea de la bitácora | ❌ Bloqueado |
| Borrar una línea | ❌ Bloqueado |
| Vaciar la tabla completa | ❌ Bloqueado |
| Borrar un usuario con historial | ❌ Bloqueado |

La protección es doble: los permisos de la base de datos no lo permiten, y un
mecanismo interno de la tabla lo bloquea incluso para quien tiene permisos
totales. Se probó con intentos reales en las pruebas automáticas.

**Importante:** el sistema registra el *intento* de acceso, no la contraseña.
Las contraseñas nunca se escriben en la bitácora ni en ningún archivo de log.

---

## 5. Seguridad aplicada en esta etapa

| Medida | Qué significa |
|---|---|
| Cuentas individuales con rol | Cada acción queda atribuida a una persona |
| Contraseñas con huella irreversible | Ni el administrador técnico puede leerlas |
| Identificador de cuenta de la API sin privilegios | Aunque la API fuera comprometida, no podría alterar la estructura de la base ni borrar datos |
| Consultas a la base no interpretan texto como órdenes | Un formulario malicioso se trata como texto, jamás como instrucción |
| Rechazo de campos no previstos | Un atacante no puede colar datos ocultos en el formulario |
| Token firmado y con vencimiento | Un token no se puede falsificar ni reutilizar indefinidamente |
| Mensaje de error único al fallar el login | No se puede averiguar qué usuarios existen probando nombres |
| Registro inviolable de operaciones | Trazabilidad completa para auditoría interna |

### Cómo se probó que resiste ataques

Se simularon **12 técnicas distintas de inyección SQL**, aplicadas en el
usuario, en la contraseña, en el nombre, en el correo y en la cédula. Ninguna
permitió entrar sin credenciales ni alteró la base. Después de los ataques, el
inicio de sesión legítimo siguió funcionando con normalidad.

También se verificó que, incluso si un atacante lograra ejecutar una orden en
la base, el identificador con el que trabaja la aplicación **no tiene permiso**
para borrar tablas, crear tablas, eliminar usuarios ni alterar la bitácora.

---

## 6. Verificación

### 6.1 Controles automáticos

```text
230 controles aprobados
  1 control omitido (corresponde a una etapa posterior del proyecto)
  0 controles fallidos
```

| Área | Controles | Qué comprueba |
|---|---:|---|
| Estructura de la información | 20 | Tablas, reglas del IVA, precios, stock, códigos, inviolabilidad de la bitácora |
| Contraseñas | 38 | Huella irreversible, sal aleatoria, reglas mínimas, resistencia a datos corruptos |
| Tokens de sesión | 37 | Firma, vencimiento, emisor, manipulación, configuración segura |
| Acceso a la API | 46 | Entrada exitosa y fallida, roles, altas, duplicados, datos inválidos |
| Auditoría | 11 | Qué se registra, qué no, y que no se puede alterar |
| Valores límite de sesión | 18 | Expiración al segundo exacto, tolerancia de reloj |
| Ataques de inyección | 42 | 12 técnicas × distintos campos, más privilegios de la base |
| Seguridad de la instalación | 19 | Contenedores, puertos, contraseñas fuera del código |

### 6.2 Verificación en vivo

| Verificación | Resultado |
|---|---|
| Servidor de la API en ejecución | ✅ Operativo |
| Documentación interactiva (Swagger) | ✅ Accesible en `/docs` |
| Estado de las dos bases | ✅ Ambas operativas |
| Rutas publicadas | ✅ Login, registro, cuenta, cierre de sesión, roles |
| Registro de eventos en la bitácora | ✅ Confirmado en las pruebas |

---

## 7. Entregables de esta semana

| Entregable | Qué es | Dónde está |
|---|---|---|
| Configuración central | Lectura de credenciales y validación de arranque | `app/config.py` |
| Protección de contraseñas | Huella scrypt con sal y política mínima | `app/core/security.py` |
| Sesiones firmadas | Emisión y validación de tokens con vencimiento | `app/core/jwt.py` |
| Auditoría automática | Interceptor de peticiones y registro de eventos | `app/core/logging.py` |
| Rutas de acceso | Login, registro, cuenta, cierre y roles | `app/api/v1/auth.py` |
| Validación de datos | Esquemas de entrada y salida | `app/schemas/usuario_schema.py` |
| Acceso a datos | Consultas parametrizadas de usuarios y bitácora | `app/models/` |
| Rol de base de datos restringido | Cuenta de la API sin privilegios de estructura | `init.sql` |
| Pruebas de la semana | 174 controles nuevos | `tests/{unit,integration,boundary,security}/` |
| Manual actualizado | Arranque, endpoints y primeros pasos | `README.md` |

---

## 8. Lo que viene

| Etapa | Contenido | Valor para la empresa |
|---|---|---|
| Semana 3 | Carga de catálogos desde Excel, PDF y Word | Se deja de digitar el inventario a mano |
| Semana 4 | Búsqueda inteligente por descripción | Se encuentra el producto aunque el nombre no coincida |
| Semana 5 | Asistente de IA para consultas | Respuestas en lenguaje natural sobre el inventario real |
| Semana 6 | Pantallas de inventario y auditoría | El personal trabaja sin consola técnica |
| Semanas 7–8 | Pruebas finales y puesta en marcha | Sistema listo para operar |

---

## 9. Recomendaciones

1. **Definir las cuentas reales** antes de la Semana 6: nombre, cédula y rol de
   cada empleado que usará el sistema.
2. **Designar quién administra las cuentas.** Debe haber al menos dos
   administradores: si uno se desactiva, el otro puede gestionar el acceso.
3. **Establecer una rutina de revisión de la bitácora.** Una auditoría que no
   se consulta no protege a nadie. Sugerencia: revisión mensual de accesos
   fallidos y altas de usuario.
4. **Comunicar la política de contraseñas** al personal: contraseñas propias,
   no compartidas, y nunca anotadas junto al equipo.
5. **Definir el plazo de inactividad** que se considere adecuado. Hoy son 30
   minutos; es un parámetro de configuración, no un cambio de código.

---

## 10. Conformidad

El suscrito declara haber ejecutado y verificado los trabajos descritos en este
informe, correspondientes a la Semana 2 del cronograma aprobado.

| Rol | Nombre | Firma | Fecha |
|---|---|---|---|
| Desarrollador | Dixon Daniel Bastias Hernandez | | |
| Representante de la empresa | | | |

---

## Anexo técnico

*Sección dirigida al personal técnico. No es necesaria para comprender el
informe.*

### A.1 Endpoints publicados

| Método | Ruta | Acceso | Respuesta |
|---|---|---|---|
| POST | `/api/v1/auth/login` | público | 200 token · 401 credenciales · 403 inactiva · 422 inválido |
| POST | `/api/v1/auth/register` | admin (público si no hay cuentas) | 201 · 400 · 401 · 403 · 409 · 422 |
| GET | `/api/v1/auth/me` | token | 200 · 401 · 403 |
| POST | `/api/v1/auth/logout` | token | 200 |
| GET | `/api/v1/auth/roles` | admin | 200 · 403 |
| GET | `/salud` | público | 200 con estado de ambas bases |
| GET | `/docs` | público | Swagger UI |

### A.2 Parámetros del hashing

| Parámetro | Valor | Justificación |
|---|---|---|
| Algoritmo | scrypt (`hashlib`) | Incluido en Python; sin dependencias externas |
| `n` | 16384 | 16 MiB de memoria por verificación |
| `r` | 8 | Requisito de scrypt para `n = 2^14` |
| `p` | 1 | Paralelismo estándar |
| Sal | 16 bytes aleatorios (`secrets`) | Única por contraseña |
| Derivación | 64 bytes | Comparación en tiempo constante (`hmac.compare_digest`) |

Formato almacenado: `scrypt$n$r$p$sal_b64$hash_b64`. Los parámetros viajan con
el hash, lo que permite elevarlos en el futuro y re-hashear de forma
transparente en el siguiente inicio de sesión (`necesita_rehash`).

### A.3 Claims del token

| Claim | Contenido |
|---|---|
| `sub` | Id del usuario |
| `usuario`, `rol` | Nombre de usuario y rol vigente al emitir |
| `tipo` | `access` (se rechazan otros tipos) |
| `iss` | Emisor configurado (`JWT_EMISOR`) |
| `iat`, `nbf`, `exp` | Emisión, inicio de validez y vencimiento |
| `jti` | Identificador único del token |

Validación: firma HS256, emisor, `exp`/`iat`/`sub` obligatorios, algoritmo
fijado en el servidor (se rechaza `alg: none` y cualquier algoritmo no
configurado). El límite de expiración es **cerrado**: al segundo exacto de
`exp` el token ya no es aceptado.

### A.4 Privilegios del rol de aplicación

| Base | Objeto | Permisos |
|---|---|---|
| `ferreteria_rag` | `productos`, `categoria`, `proveedores`, `archivos_subidos` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `ferreteria_rag` | Secuencias | `USAGE`, `SELECT` |
| `ferreteria_usuarios` | `rol` | `SELECT` |
| `ferreteria_usuarios` | `usuarios` | `SELECT`, `INSERT`, `UPDATE` (sin `DELETE`) |
| `ferreteria_usuarios` | `bitacora` | `SELECT`, `INSERT` |
| `ferreteria_usuarios` | Esquema `public` | `USAGE` (sin `CREATE`) |
| Ambos | Conexión | `CONNECT` |

Además: `statement_timeout = 15s` e `idle_in_transaction_session_timeout = 30s`.

### A.5 Variables de entorno nuevas

| Variable | Uso |
|---|---|
| `APP_DB_PASSWORD` | Contraseña del rol `app_ferreteria` (mínimo 16 caracteres) |
| `DATABASE_URL_RAG` | DSN de la API al catálogo |
| `DATABASE_URL_USUARIOS` | DSN de la API a usuarios y auditoría |
| `ADMIN_DATABASE_URL` | DSN de administración (pruebas y tareas puntuales) |
| `JWT_SECRET` | Clave de firma (mínimo 32 caracteres) |
| `JWT_ALGORITHM` | `HS256` por defecto; solo se admiten HS256/384/512 |
| `JWT_EXPIRACION_MINUTOS` | 30 por defecto |
| `JWT_EMISOR` | Identificador del emisor del token |
| `ENTORNO` | `desarrollo` o `produccion` |
| `CORS_ORIGENES` | Orígenes permitidos para AJAX |
| `CONFIAR_EN_PROXY` | Usa `X-Forwarded-For` solo detrás de un proxy propio |

`app/config.py` valida al arrancar: sin `JWT_SECRET` válido o sin DSN la
aplicación **no inicia**. En `produccion` rechaza además el secreto de ejemplo.

### A.6 Ejecución de las pruebas

```bash
venv\Scripts\python.exe -m pytest tests/ -q

# Por tipo
pytest tests/unit -q          # hashing, JWT y esquema SQL
pytest tests/integration -q   # API de punta a punta
pytest tests/boundary -q      # expiración exacta del JWT
pytest tests/security -q      # inyección SQL y permisos
```

Las pruebas de integración clonan las bases como `ferreteria_*_test` al
iniciar la sesión y las eliminan al terminar. La clonación exige que no haya
otras conexiones abiertas sobre las bases originales (pgAdmin incluido).

### A.7 Archivos creados o modificados

| Archivo | Estado |
|---|---|
| `app/config.py` | Nuevo |
| `app/core/security.py` | Nuevo (reemplaza el `segurity.py` del scaffold) |
| `app/core/jwt.py` | Nuevo |
| `app/core/logging.py` | Nuevo |
| `app/db/session.py` | Nuevo (pools diferidos, un pool por base) |
| `app/models/usuario.py`, `app/models/bitacora.py` | Nuevos |
| `app/schemas/usuario_schema.py` | Nuevo |
| `app/api/deps.py` | Nuevo (autenticación y roles) |
| `app/api/v1/auth.py`, `app/api/api_router.py` | Nuevos |
| `app/main.py` | Nuevo |
| `init.sql` | Rol `app_ferreteria` y sus privilegios |
| `docker-compose.yml` | Propaga `APP_DB_PASSWORD` |
| `.env`, `.env.example`, `requirements.txt`, `README.md` | Actualizados |
| `tests/conftest.py` y 5 archivos de prueba | Nuevos |

### A.8 Limitaciones conocidas

| Limitación | Impacto | Mitigación prevista |
|---|---|---|
| Sin límite de intentos de login | Fuerza bruta posible | Bloqueo temporal por IP/usuario (Semana 6) |
| El cierre de sesión no invalida el token ya emitido | El token vive hasta su `exp` | Lista de revocación o tokens cortos con refresco |
| `fail2ban`/WAF no configurado | Depende del hosting | Configurar al desplegar en VPS (Semana 8) |
| Sin HTTPS en desarrollo | El token viaja en claro en red local | Certificado TLS obligatorio en producción |
| Sin segundo factor (2FA) | Solo contraseña | Evaluar por costo/beneficio |

---

*Documento generado como parte del entregable de la Semana 2.*

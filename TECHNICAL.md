# SEA-API - Documentacion Tecnica

Documento tecnico que describe la arquitectura interna, decisiones de diseno, librerias utilizadas y flujos de seguridad del backend del Sistema de Evaluacion Academica.

---

## Tabla de Contenidos

- [Arquitectura General](#arquitectura-general)
- [Dependencias y Librerias](#dependencias-y-librerias)
- [Modelo de Datos](#modelo-de-datos)
- [Autenticacion y JWT](#autenticacion-y-jwt)
- [Cifrado de Contrasenas en Transito](#cifrado-de-contrasenas-en-transito)
- [Almacenamiento de Contrasenas](#almacenamiento-de-contrasenas)
- [Recuperacion de Contrasena](#recuperacion-de-contrasena)
- [Sistema de Roles y Permisos](#sistema-de-roles-y-permisos)
- [Flujo de Envio de Correos](#flujo-de-envio-de-correos)
- [Sistema de Auditoria](#sistema-de-auditoria)
- [Rate Limiting](#rate-limiting)
- [Paginacion y Respuestas Estandar](#paginacion-y-respuestas-estandar)
- [Validacion y Sanitizacion](#validacion-y-sanitizacion)
- [Logging](#logging)
- [Avance Academico Automatico](#avance-academico-automatico)
- [Exportacion de Calificaciones](#exportacion-de-calificaciones)
- [Seguridad HTTP](#seguridad-http)
- [Middleware Stack](#middleware-stack)
- [Despliegue y Produccion](#despliegue-y-produccion)

---

## Arquitectura General

El proyecto sigue una arquitectura **Django + DRF (Django REST Framework)** organizada en 9 apps independientes con separacion por dominio:

```
Request HTTP
    |
    v
[CORS Middleware] --> [Security Middleware] --> [WhiteNoise] --> [Session]
    |
    v
[CSRF] --> [Auth Middleware] --> [RequestContext Middleware] --> [AuditUser Middleware]
    |
    v
[URL Router (config/urls.py)]
    |
    v
[App Router (apps/*/urls.py)]
    |
    v
[View (APIView/ViewSet)] --> [Serializer] --> [Service] --> [Model/ORM]
    |
    v
[Response estandar (utils/responses.py)]
```

### Patron de diseno

Cada app sigue el patron **View -> Serializer -> Service -> Model**:

- **View**: Recibe la peticion HTTP, valida permisos, delega al servicio.
- **Serializer**: Valida datos de entrada/salida, transforma entre JSON y objetos Python.
- **Service**: Contiene la logica de negocio. Los views no manipulan datos directamente.
- **Model**: Define el esquema de datos y relaciones. Usa Django ORM para queries.

Esta separacion permite que la logica de negocio sea reutilizable y testeable independientemente de la capa HTTP.

---

## Dependencias y Librerias

### Framework y Core

| Libreria | Para que se usa |
|---|---|
| **Django 5.0** | Framework web principal. Provee ORM, migraciones, sistema de usuarios, middleware, templates y administracion. |
| **djangorestframework 3.14.0** | Extension de Django para construir APIs REST. Provee serializers (validacion/transformacion de datos), vistas genericas, autenticacion, throttling y negociacion de contenido. |
| **asgiref 3.11.1** | Dependencia interna de Django para soporte asincrono (ASGI). No se usa directamente. |
| **sqlparse 0.5.5** | Dependencia interna de Django para parsear sentencias SQL en migraciones y debug. |

### Autenticacion

| Libreria | Para que se usa |
|---|---|
| **djangorestframework-simplejwt 5.3.1** | Implementacion de JWT para DRF. Genera tokens de acceso y refresco, los valida, y extrae claims (datos del usuario) sin consultar la base de datos en cada peticion. |
| **PyJWT 2.11.0** | Libreria base de Python para codificar/decodificar tokens JWT. SimpleJWT la usa internamente. |

### Seguridad y Cifrado

| Libreria | Para que se usa |
|---|---|
| **pycryptodome 3.21.0** | Implementa cifrado AES-256-GCM para proteger datos sensibles (contrasenas) en transito entre frontend y backend. Tambien soporta AES-CBC como fallback para compatibilidad con CryptoJS. |

### Base de Datos

| Libreria | Para que se usa |
|---|---|
| **psycopg 3.3.3** | Driver PostgreSQL de tercera generacion para Python. Permite que Django se comunique con PostgreSQL. Version pura en Python. |
| **psycopg-binary 3.3.3** | Extension compilada en C de psycopg para mejor rendimiento en queries. Se instala junto con la version pura como optimizacion. |

### CORS

| Libreria | Para que se usa |
|---|---|
| **django-cors-headers 4.3.1** | Middleware que agrega headers CORS (Cross-Origin Resource Sharing) a las respuestas. Permite que el frontend (en otro dominio/puerto) se comunique con la API. Sin esto, el navegador bloquea las peticiones cross-origin. |

### Documentacion API

| Libreria | Para que se usa |
|---|---|
| **drf-spectacular 0.27.0** | Genera automaticamente el schema OpenAPI 3.0 a partir de los serializers y views de DRF. Provee Swagger UI (interfaz interactiva para probar endpoints) y ReDoc (documentacion estatica). |

### Email

| Libreria | Para que se usa |
|---|---|
| **django-anymail 12.0** | Backend de email que conecta Django con proveedores transaccionales como Brevo (SendinBlue). Envia correos via API HTTPS en lugar de SMTP, lo cual evita problemas de puertos bloqueados en hostings como Render. |

### Exportacion de Archivos

| Libreria | Para que se usa |
|---|---|
| **openpyxl 3.1.2** | Crea y manipula archivos Excel (.xlsx). Se usa para exportar calificaciones de examenes por grupo en formato de hoja de calculo. |
| **reportlab 4.2.0** | Genera archivos PDF programaticamente. Se usa para exportar reportes de calificaciones en formato PDF con formato y tablas. |

### Tareas Programadas

| Libreria | Para que se usa |
|---|---|
| **APScheduler 3.10.4** | Scheduler en proceso (no requiere cron externo ni Celery). Ejecuta tareas programadas dentro del mismo proceso de Django. Se usa para avanzar automaticamente los niveles academicos de los grupos al inicio de cada periodo. |

### Servidor y Produccion

| Libreria | Para que se usa |
|---|---|
| **gunicorn 22.0.0** | Servidor WSGI de produccion para Python. Reemplaza al servidor de desarrollo de Django (`runserver`) en produccion. Maneja multiples workers para atender peticiones concurrentes. |
| **whitenoise 6.7.0** | Sirve archivos estaticos (CSS, JS, imagenes) directamente desde la aplicacion Python sin necesidad de Nginx o Apache. Comprime y cachea archivos estaticos en produccion. |

### Utilidades

| Libreria | Para que se usa |
|---|---|
| **python-decouple 3.8** | Lee variables de entorno desde archivos `.env`. Permite separar la configuracion sensible (claves, passwords) del codigo fuente. |
| **loguru 0.7.2** | Libreria de logging mas amigable que el modulo `logging` estandar de Python. Permite rotacion automatica de archivos, compresion, y formato estructurado sin configuracion compleja. |
| **chardet 5.2.0** | Detecta automaticamente la codificacion de caracteres de archivos de texto. Se usa para manejar correctamente archivos subidos con diferentes encodings (UTF-8, Latin-1, etc.). |
| **pytz 2026.1.post1** | Base de datos de zonas horarias. Permite trabajar con la zona `America/Mexico_City` para fechas y periodos academicos. |
| **tzdata 2025.3** | Datos de zonas horarias del sistema IANA. Complementa a pytz en sistemas que no tienen los datos de timezone instalados (como algunos contenedores Docker). |

---

## Modelo de Datos

### Jerarquia Academica

```
Generation (2024, 2025...)
    |
    +-- Group (2024-A, 2024-B...)     <-- tiene academic_level calculado
         |
         +-- StudentProfile (alumnos asignados)
         |
         +-- GroupTeacherAssignment (profesor + materia asignada)

Subject (Matematicas nivel 3, Fisica nivel 2...)
    |
    +-- Unit (Unidad 1, Unidad 2...)
    |
    +-- Question (banco de preguntas por materia)
         |
         +-- Answer (opciones de respuesta)
```

### Flujo de Examenes

```
Exam (creado por profesor, vinculado a materia)
    |
    +-- ExamQuestion (preguntas seleccionadas del banco)
    |
    +-- ExamGroupAssignment (asignado a grupos)
    |
    +-- ExamAssignment (instancia por estudiante)
         |
         +-- StudentAnswer (respuesta a cada pregunta)
```

### Usuario y Perfiles

El modelo `User` extiende `AbstractUser` de Django y agrega:
- `id_user`: Primary key personalizada
- `matricula`: Identificador unico del alumno/profesor
- `role`: Enum con valores `student`, `teacher`, `admin`
- `status`: Estado activo/inactivo

Cada rol tiene un perfil asociado:
- **StudentProfile**: Vinculo 1:1 con User, referencia al grupo asignado
- **TeacherProfile**: Vinculo 1:1 con User, relacion M2M con materias

---

## Autenticacion y JWT

### Flujo de Login

```
1. Cliente envia POST /api/auth/login/ con {email, password}
2. AuthenticationService.authenticate_user() valida credenciales
3. Django verifica password contra hash PBKDF2-SHA256 en BD
4. Si es valido, se generan dos tokens JWT:
   - Access Token (60 min): para autenticar peticiones
   - Refresh Token (24 hrs): para obtener nuevos access tokens
5. Se retornan tokens + datos del usuario (id, email, role, full_name)
```

### Estructura del Token JWT

Un token JWT tiene tres partes separadas por puntos: `header.payload.signature`

```
Header:  {"alg": "HS256", "typ": "JWT"}
Payload: {"user_id": 1, "email": "...", "role": "admin", "exp": 1713400000}
Firma:   HMAC-SHA256(header + payload, JWT_SECRET_KEY)
```

- **HS256**: El token se firma con una clave secreta compartida (`JWT_SECRET_KEY`). El servidor puede verificar que el token no fue modificado recalculando la firma.
- **Stateless**: El servidor NO almacena sesiones. Toda la informacion necesaria esta dentro del token. Esto permite escalar horizontalmente sin compartir estado entre servidores.

### Autenticacion en Peticiones Protegidas

```
1. Cliente incluye header: Authorization: Bearer <access_token>
2. AuditJWTAuthentication (middleware custom) intercepta
3. SimpleJWT verifica firma, expiracion, y extrae claims
4. Se construye objeto User desde los claims (sin query a BD)
5. Se establece variable de sesion en PostgreSQL para auditoria
6. La peticion continua al view con request.user disponible
```

### Refresh de Token

Cuando el access token expira (60 min), el cliente envia el refresh token para obtener uno nuevo sin re-autenticarse:

```
POST /api/auth/refresh/ con {refresh: "eyJ..."}
-> Retorna nuevo {access: "eyJ..."}
```

---

## Cifrado de Contrasenas en Transito

### Problema

Las contrasenas no deben viajar como texto plano en el cuerpo de la peticion HTTP, incluso con HTTPS. Se implementa una capa adicional de cifrado a nivel de aplicacion.

### Solucion: AES-256-GCM

El endpoint `POST /api/auth/change-password/` recibe un payload cifrado con **AES-256-GCM** (Advanced Encryption Standard con Galois/Counter Mode).

### Como funciona el flujo

```
FRONTEND                                    BACKEND
--------                                    -------
1. Usuario escribe:
   current_password: "mi_pass_actual"
   new_password: "mi_nueva_pass"

2. Se genera un nonce aleatorio
   de 12 bytes (96 bits)

3. Se cifra el JSON con AES-256-GCM:
   - Clave: ENCRYPTION_KEY (compartida)
   - Nonce: aleatorio de 12 bytes
   - Resultado: ciphertext + auth_tag

4. Se envia como base64:                   5. Recibe el payload cifrado
   {                                        6. Decodifica base64
     "encrypted_data": "base64(             7. Extrae nonce (primeros 12 bytes)
       nonce + ciphertext + tag             8. Extrae tag (ultimos 16 bytes)
     )"                                     9. Descifra con AES-256-GCM
   }                                       10. Obtiene JSON original
                                           11. Valida y procesa cambio
```

### Detalles del cifrado

- **AES-256**: Cifrado simetrico con clave de 256 bits (32 bytes). Considerado seguro por NIST.
- **GCM (Galois/Counter Mode)**: Modo de operacion que provee tanto **confidencialidad** (nadie puede leer el contenido) como **autenticidad** (nadie puede modificar el contenido sin ser detectado).
- **Nonce (96 bits)**: Numero aleatorio usado una sola vez. Previene que dos mensajes identicos produzcan el mismo ciphertext.
- **Authentication Tag (128 bits)**: Verificador de integridad. Si alguien modifica el ciphertext, el descifrado falla.

### Implementacion (`utils/crypto.py`)

```python
# Cifrado (conceptual)
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
ciphertext, tag = cipher.encrypt_and_digest(plaintext)
resultado = nonce + ciphertext + tag  # todo concatenado

# Descifrado
nonce = data[:12]          # primeros 12 bytes
tag = data[-16:]           # ultimos 16 bytes
ciphertext = data[12:-16]  # el resto
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
plaintext = cipher.decrypt_and_verify(ciphertext, tag)
```

### Fallback AES-CBC

Para compatibilidad con implementaciones anteriores que usaban CryptoJS en el frontend, el sistema tambien soporta descifrar con **AES-CBC** usando la derivacion de clave `EVP_BytesToKey` (formato OpenSSL). Este modo solo se usa para leer datos antiguos; todo cifrado nuevo usa GCM.

### Clave de cifrado

La `ENCRYPTION_KEY` es una clave de 32 bytes codificada en base64, configurada como variable de entorno. Tanto frontend como backend comparten esta misma clave (cifrado simetrico).

---

## Almacenamiento de Contrasenas

Las contrasenas **nunca** se almacenan en texto plano. Django usa **PBKDF2-SHA256** por defecto:

```
password -> PBKDF2(password, salt, iterations=870000) -> hash
```

- **PBKDF2**: Password-Based Key Derivation Function 2. Aplica una funcion hash repetidamente (870,000 iteraciones en Django 5.0) para hacer extremadamente lento un ataque de fuerza bruta.
- **Salt**: Valor aleatorio unico por contrasena. Evita que dos usuarios con la misma contrasena tengan el mismo hash.
- **SHA-256**: Funcion hash criptografica de 256 bits usada como primitiva dentro de PBKDF2.

El hash almacenado en BD tiene este formato:
```
pbkdf2_sha256$870000$<salt>$<hash>
```

Para verificar un login, Django aplica PBKDF2 al password recibido con el mismo salt y compara el resultado con el hash almacenado.

---

## Recuperacion de Contrasena

Flujo de 3 pasos sin enviar contrasenas por email:

### Paso 1: Solicitar codigo

```
POST /api/users/password-recovery/request/
Body: {"email": "usuario@ejemplo.com"}
```

1. Se busca al usuario por email
2. Se genera un codigo aleatorio de 6 digitos
3. Se guarda en `PasswordResetCode` con TTL de 15 minutos
4. Se envia por email usando plantilla HTML via Brevo
5. **Seguridad**: Si el email no existe, se responde con el mismo mensaje exitoso para no revelar que emails estan registrados

### Paso 2: Verificar codigo

```
POST /api/users/password-recovery/verify/
Body: {"email": "usuario@ejemplo.com", "code": "482916"}
```

1. Se busca el codigo mas reciente para ese email
2. Se verifica que no haya expirado (15 min) y no haya sido usado
3. Retorna confirmacion sin modificar nada

### Paso 3: Restablecer contrasena

```
POST /api/users/password-recovery/reset/
Body: {"email": "usuario@ejemplo.com", "code": "482916", "new_password": "nueva_pass"}
```

1. Se valida el codigo nuevamente
2. Se actualiza la contrasena con `user.set_password()` (genera nuevo hash PBKDF2)
3. Se marca el codigo como usado (`is_used = True`)
4. El codigo no puede reutilizarse

---

## Sistema de Roles y Permisos

### Clases de permiso personalizadas

Definidas en cada app, controlan acceso a nivel de view:

| Clase | Permite acceso a |
|---|---|
| `IsAdmin` | Solo usuarios con `role = 'admin'` |
| `IsTeacherOrAdmin` | Usuarios con `role = 'teacher'` o `role = 'admin'` |
| `IsAuthenticatedStudent` | Solo usuarios con `role = 'student'` |

### Header X-Active-Role

Algunas vistas aceptan el header `X-Active-Role` para que un usuario con multiples privilegios pueda actuar en un rol especifico (util para admins que tambien son profesores).

### Proteccion por endpoint

Cada view declara sus permisos:
```python
class UserListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
```

Si un usuario autenticado no tiene el rol requerido, recibe `403 Forbidden`.

---

## Flujo de Envio de Correos

### Proveedor: Brevo (SendinBlue)

Se usa **django-anymail** como backend de email, conectado a la API HTTPS de Brevo. No se usa SMTP tradicional.

### Por que Brevo y no SMTP directo

Muchos hostings (como Render) bloquean el puerto 25/587 para prevenir spam. Brevo ofrece una API REST por HTTPS (puerto 443) que no tiene esta limitacion.

### Plantillas HTML

Las plantillas estan en `templates/email/` y se renderizan con el motor de templates de Django:

- **welcome_account.vm**: Email de bienvenida con credenciales iniciales cuando un admin crea un usuario
- **password_reset.vm**: Email con el codigo de 6 digitos para recuperacion de contrasena

### Flujo tecnico

```python
# En el servicio
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

html_content = render_to_string('email/welcome_account.vm', context)
email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
email.attach_alternative(html_content, "text/html")
email.send()
# django-anymail intercepta y envia via API de Brevo
```

### Comportamiento ante fallos

Si el envio de email falla, la operacion principal (crear usuario, generar codigo) **no se revierte**. Los errores se registran en logs pero no bloquean al usuario.

---

## Sistema de Auditoria

### Arquitectura: Triggers de PostgreSQL

A diferencia de soluciones basadas en Django (signals, middleware), la auditoria se implementa a nivel de base de datos con **triggers PostgreSQL**.

### Como funciona

```
1. Cualquier INSERT/UPDATE/DELETE en tablas auditadas dispara un trigger
2. El trigger inserta un registro en la tabla audit_log con:
   - table_name: tabla afectada
   - operation_type: INSERT, UPDATE, DELETE
   - old_values: JSON con valores anteriores (en UPDATE/DELETE)
   - new_values: JSON con valores nuevos (en INSERT/UPDATE)
   - changed_at: timestamp
   - db_user: usuario de PostgreSQL
   - app_user: usuario de la aplicacion (del JWT)
   - client_addr: IP del cliente
```

### Vinculo con el usuario de la aplicacion

El middleware `AuditUserMiddleware` establece una variable de sesion en PostgreSQL:

```python
# Al recibir una peticion autenticada
SET LOCAL app.current_user = '42';  # ID del usuario JWT

# El trigger PostgreSQL lee esta variable
current_setting('app.current_user', true)
```

Esto permite que el trigger sepa que usuario de la *aplicacion* (no solo el usuario de BD) realizo el cambio.

### Modelo Django

```python
class AuditLog(models.Model):
    class Meta:
        managed = False  # Django NO crea ni migra esta tabla
        db_table = 'audit_log'
```

`managed = False` significa que la tabla es creada por el script SQL (`init.sql`), no por las migraciones de Django.

---

## Rate Limiting

Implementado con el sistema de throttling de DRF:

| Scope | Limite | Endpoint |
|---|---|---|
| `anon` | 30/minuto | Todos (anonimo) |
| `user` | 60/minuto | Todos (autenticado) |
| `login` | 5/minuto | `/api/auth/login/` |
| `student_assignments` | 60/minuto | `/api/exams/exam-assignments/my-assignments/` |
| `grade_export` | 30/minuto | Exportacion Excel/PDF |

Los limites son configurables via variables de entorno (`THROTTLE_ANON_RATE`, etc.).

### Funcionamiento

DRF rastrea peticiones por IP (anonimos) o por usuario (autenticados) usando el cache de Django. Si se excede el limite, retorna `429 Too Many Requests` con header `Retry-After`.

---

## Paginacion y Respuestas Estandar

### Paginacion Global

Todas las vistas que retornan listas usan `GlobalPagination`:

```json
{
  "count": 150,
  "total_pages": 15,
  "current_page": 1,
  "page_size": 10,
  "next": "http://.../api/users/?page=2",
  "previous": null,
  "results": [...]
}
```

Parametros: `?page=2&page_size=20` (maximo 100 por pagina).

### Formato de Respuesta Estandar

Todas las respuestas siguen este formato via `utils/responses.py`:

```json
// Exitosa
{
  "success": true,
  "data": { ... },
  "message": "Operacion exitosa"
}

// Error
{
  "success": false,
  "data": null,
  "message": "Descripcion del error",
  "errors": { "field": ["detalle del error"] }
}
```

---

## Validacion y Sanitizacion

### Sanitizacion de Entrada (`utils/sanitizers.py`)

- **Deteccion de HTML**: Rechaza campos que contengan tags HTML para prevenir XSS almacenado
- **Normalizacion de nombres**: Elimina espacios multiples, trim
- **Longitud de busqueda**: Limita queries de busqueda para prevenir DoS por regex

### Validacion (`utils/validators.py`)

- **Email**: Formato valido y unicidad
- **Matricula**: Formato esperado para identificadores escolares
- **Password**: Minimo 8 caracteres, no puede ser solo numeros

### Validacion en Serializers

Cada serializer de DRF valida campos a nivel de tipo, formato y reglas de negocio:

```python
class RegisterUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['student', 'teacher', 'admin'])
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email ya registrado")
        return value
```

---

## Logging

### Libreria: Loguru

Reemplaza el modulo `logging` estandar por una interfaz mas simple:

```python
from loguru import logger

logger.info("Usuario {user_id} inicio sesion", user_id=42)
logger.error("Fallo al enviar email: {error}", error=str(e))
```

### Configuracion

| Parametro | Valor |
|---|---|
| Directorio | `logs/` |
| Rotacion | 10 MB por archivo |
| Retencion | 2 dias |
| Compresion | ZIP |
| Archivos | `debug.log`, `info.log`, `warning.log`, `error.log`, `critical.log` |

Cada nivel de severidad tiene su propio archivo, lo que facilita filtrar problemas en produccion.

---

## Avance Academico Automatico

### Problema

Los grupos deben subir de nivel academico al inicio de cada periodo (cuatrimestre). Hacer esto manualmente es propenso a errores.

### Solucion: APScheduler

APScheduler se ejecuta dentro del proceso de Django (no requiere Celery, Redis, ni cron externo).

### Configuracion tecnica

```python
# En apps/academic/apps.py -> ready()
scheduler = BackgroundScheduler(timezone='America/Mexico_City')
scheduler.add_job(
    advance_academic_levels,
    trigger='cron',
    month='1,5,9',    # Enero, Mayo, Septiembre
    day=1,
    hour=0,
    minute=0
)
scheduler.start()
```

### Formula de calculo

```
academic_level = ((year_actual - year_generacion) * 3) + (periodo_actual - periodo_inicio) + 1
```

Ejemplo: Generacion 2024, periodo Mayo-Agosto 2025:
```
= ((2025 - 2024) * 3) + (2 - 1) + 1
= 3 + 1 + 1
= 5 (quinto cuatrimestre)
```

El nivel no puede exceder `total_levels` de la generacion.

---

## Exportacion de Calificaciones

### Excel (openpyxl)

```
GET /api/exams/{id}/grades/groups/{gid}/export/excel/
```

Genera un archivo `.xlsx` con:
- Encabezados: Nombre, Matricula, Calificacion, Estado (Aprobado/Reprobado)
- Datos de cada estudiante del grupo para ese examen

### PDF (reportlab)

```
GET /api/exams/{id}/grades/groups/{gid}/export/pdf/
```

Genera un archivo `.pdf` con tabla formateada de calificaciones.

Ambos se generan en memoria (sin archivos temporales en disco) y se envian como respuesta HTTP con `Content-Disposition: attachment`.

---

## Seguridad HTTP

### Headers de seguridad (settings.py)

| Configuracion | Valor | Proposito |
|---|---|---|
| `SECURE_BROWSER_XSS_FILTER` | `True` | Activa filtro XSS del navegador |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Previene MIME sniffing |
| `X_FRAME_OPTIONS` | `DENY` | Previene clickjacking (no permite iframes) |
| `CSRF_COOKIE_HTTPONLY` | `True` | Cookie CSRF no accesible desde JavaScript |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | 10 MB | Limite de tamano de upload |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | 10 MB | Limite de archivo en memoria |

### CORS

Configurado via `django-cors-headers`:
- **Desarrollo**: Origenes especificos en `CORS_ALLOWED_ORIGINS` (ej: `http://localhost:5173`)
- **Produccion**: Solo origenes del frontend desplegado
- **Credenciales**: `CORS_ALLOW_CREDENTIALS = True` (permite envio de cookies/tokens)
- **Headers custom**: Se permite `X-Active-Role` para seleccion de rol activo

---

## Middleware Stack

Orden de ejecucion (cada peticion pasa por todos en orden):

```
1. CorsMiddleware          -> Agrega headers CORS a la respuesta
2. SecurityMiddleware      -> Aplica headers de seguridad HTTP
3. WhiteNoiseMiddleware    -> Sirve archivos estaticos en produccion
4. SessionMiddleware       -> Maneja sesiones (requerido por Django admin)
5. CommonMiddleware        -> Normalizacion de URLs, Content-Length
6. CsrfViewMiddleware      -> Proteccion CSRF (DRF lo desactiva para API)
7. AuthenticationMiddleware -> Carga usuario de sesion Django
8. RequestContextMiddleware -> Almacena request en thread-local (para acceso en modelos)
9. AuditUserMiddleware      -> Limpia variable de sesion PostgreSQL post-request
10. MessageMiddleware       -> Framework de mensajes Django
11. XFrameOptionsMiddleware -> Header X-Frame-Options: DENY
```

---

## Despliegue y Produccion

### Stack de produccion

```
Internet -> Render (PaaS) -> Gunicorn (WSGI) -> Django
                              |
                              +-> WhiteNoise (archivos estaticos)
                              |
                              +-> Brevo API (emails)
                              |
                              +-> Supabase PostgreSQL (base de datos)
```

### Gunicorn

Servidor WSGI que corre multiples workers para manejar peticiones concurrentes. Reemplaza al servidor de desarrollo de Django que solo maneja una peticion a la vez.

### WhiteNoise

En produccion, `python manage.py collectstatic` recopila todos los archivos estaticos y WhiteNoise los sirve comprimidos y con cache headers, sin necesidad de un servidor web separado (Nginx/Apache).

### Render.yaml

```yaml
services:
  - type: web
    buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput
    startCommand: python manage.py migrate && gunicorn config.wsgi
```

Las migraciones se ejecutan automaticamente al iniciar el servicio.

---

## Resumen de Flujos Clave

### Login completo
```
Cliente -> POST /login {email, pass}
        -> Django auth (PBKDF2 verify)
        -> Genera JWT (access + refresh)
        -> Retorna tokens + user data
```

### Cambio de contrasena
```
Cliente -> Cifra {old_pass, new_pass} con AES-256-GCM
        -> POST /change-password {encrypted_data}
        -> Backend descifra con clave compartida
        -> Verifica old_pass contra hash en BD
        -> Genera nuevo hash PBKDF2 para new_pass
        -> Actualiza en BD
```

### Flujo de examen
```
Admin crea usuarios -> Profesor crea examen + selecciona preguntas del banco
                    -> Profesor asigna examen a grupos
                    -> Sistema crea ExamAssignment por cada estudiante
                    -> Estudiante ve asignacion en /my-assignments
                    -> Estudiante responde y envia con /submit
                    -> Auto-calificacion (opcion multiple) o manual (abiertas)
                    -> Profesor exporta calificaciones (Excel/PDF)
                    -> Reportes disponibles por examen/grupo/estudiante
```

---

Documentacion tecnica del proyecto SEA-API - Legacy Devs

# SEA-API - Sistema de Evaluacion Academica

API REST para la gestion de examenes y evaluaciones academicas construida con Django REST Framework y PostgreSQL.

---

## Tabla de Contenidos

- [Caracteristicas](#caracteristicas)
- [Tecnologias](#tecnologias)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Configuracion Inicial](#configuracion-inicial)
- [Variables de Entorno](#variables-de-entorno)
- [Base de Datos](#base-de-datos)
- [Ejecutar el Proyecto](#ejecutar-el-proyecto)
- [Documentacion API](#documentacion-api)
- [Endpoints](#endpoints)
- [Roles de Usuario](#roles-de-usuario)
- [Avance Automatico de Niveles](#avance-automatico-de-niveles-academicos)
- [Despliegue](#despliegue)
- [Solucion de Problemas](#solucion-de-problemas)

---

## Caracteristicas

- Autenticacion JWT con tokens de acceso y refresco
- Gestion de usuarios con tres roles (Estudiante, Profesor, Administrador)
- Gestion academica: generaciones, periodos, grupos, materias y unidades
- Banco de preguntas con soporte para opcion multiple, seleccion multiple, abiertas y codigo
- Creacion, asignacion y calificacion de examenes
- Auto-calificacion para preguntas de opcion multiple y calificacion manual para abiertas/codigo
- Recuperacion de contrasena via codigo de 6 digitos por email
- Exportacion de calificaciones a Excel y PDF
- Reportes por examen, grupo y estudiante
- Avance automatico de niveles academicos con APScheduler
- Auditoria de cambios via triggers de PostgreSQL
- Rate limiting configurable por endpoint
- Documentacion interactiva con Swagger/ReDoc
- Envio de correos via Brevo (SendinBlue) API
- Cifrado AES-256-GCM para datos sensibles en transito

---

## Tecnologias

| Tecnologia | Version | Uso |
|---|---|---|
| Python | 3.9+ | Lenguaje principal |
| Django | 5.0 | Framework web |
| Django REST Framework | 3.14.0 | API REST |
| PostgreSQL | 14+ | Base de datos |
| SimpleJWT | 5.3.1 | Autenticacion JWT |
| APScheduler | 3.10.4 | Tareas programadas |
| drf-spectacular | 0.27.0 | Documentacion OpenAPI |
| Brevo (django-anymail) | 12.0 | Envio de emails |
| pycryptodome | 3.21.0 | Cifrado AES-256 |
| openpyxl | 3.1.2 | Exportacion Excel |
| reportlab | 4.2.0 | Exportacion PDF |
| gunicorn | 22.0.0 | Servidor WSGI produccion |
| whitenoise | 6.7.0 | Archivos estaticos |
| loguru | 0.7.2 | Logging estructurado |

---

## Estructura del Proyecto

```
SEA-api/
├── apps/
│   ├── authentication/     # Login, refresh token, cambio de contrasena
│   ├── users/              # CRUD usuarios, perfiles, recuperacion de contrasena
│   ├── academic/           # Generaciones, periodos, grupos, materias, unidades
│   ├── questions/          # Banco de preguntas y respuestas
│   ├── exams/              # Examenes, asignaciones, exportacion de calificaciones
│   ├── answers/            # Respuestas de estudiantes, calificacion manual
│   ├── reports/            # Reportes por examen, grupo, estudiante
│   ├── audit/              # Logs de auditoria (PostgreSQL triggers)
│   └── core/               # Modelo base, middleware, utilidades
├── config/
│   ├── settings.py         # Configuracion Django
│   ├── urls.py             # URLs raiz
│   ├── wsgi.py             # WSGI
│   └── asgi.py             # ASGI
├── utils/
│   ├── crypto.py           # Cifrado/descifrado AES-256-GCM
│   ├── responses.py        # Formato estandar de respuestas
│   ├── pagination.py       # Paginacion global
│   ├── validators.py       # Validadores personalizados
│   └── sanitizers.py       # Sanitizacion de entrada
├── templates/email/         # Plantillas HTML para correos
├── scripts/                 # Scripts auxiliares
├── docker-compose.yml       # PostgreSQL local con Docker
├── render.yaml              # Configuracion de despliegue en Render
├── requirements.txt         # Dependencias Python
├── init.sql                 # Script de inicializacion de BD
└── .env.example             # Plantilla de variables de entorno
```

---

## Configuracion Inicial

### 1. Clonar el Repositorio

```bash
git clone <url-del-repositorio>
cd SEA-api
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales. Consulta la seccion [Variables de Entorno](#variables-de-entorno) para el detalle de cada variable.

### 4. Configurar base de datos

Opcion A - Docker (recomendado para desarrollo):
```bash
docker-compose up -d
```

Opcion B - PostgreSQL local:
```bash
psql -U postgres -c "CREATE DATABASE SEA_database;"
psql -U postgres -d SEA_database -f init.sql
```

### 5. Ejecutar migraciones

```bash
python3 manage.py migrate
```

### 6. Crear usuario administrador

```bash
python3 manage.py createsuperuser
```

O usa el script SQL que crea un admin por defecto al ejecutar `init.sql`.

---

## Variables de Entorno

| Variable | Descripcion | Valor por defecto |
|---|---|---|
| `SECRET_KEY` | Clave secreta de Django | Requerido en produccion |
| `DEBUG` | Modo debug | `True` |
| `ALLOWED_HOSTS` | Hosts permitidos (separados por coma) | `localhost,127.0.0.1` |
| `CORS_ALLOW_ALL` | Permitir todos los origenes CORS | `False` |
| `CORS_ALLOWED_ORIGINS` | Origenes permitidos (separados por coma) | - |
| `ENCRYPTION_KEY` | Clave AES-256 en base64 (32 bytes) | **Requerido** |
| `JWT_SECRET_KEY` | Clave de firma JWT | - |
| `JWT_ALGORITHM` | Algoritmo JWT | `HS256` |
| `JWT_ACCESS_TOKEN_LIFETIME` | Duracion access token (minutos) | `60` |
| `JWT_REFRESH_TOKEN_LIFETIME` | Duracion refresh token (minutos) | `1440` |
| `USE_DATABASE` | Usar PostgreSQL (`True`) o mock (`False`) | `True` |
| `DB_NAME` | Nombre de la base de datos | - |
| `DB_USER` | Usuario de la base de datos | - |
| `DB_PASSWORD` | Contrasena de la base de datos | - |
| `DB_HOST` | Host de la base de datos | `localhost` |
| `DB_PORT` | Puerto de la base de datos | `5432` |
| `BREVO_API_KEY` | API key de Brevo para envio de emails | - |
| `DEFAULT_FROM_EMAIL` | Email remitente | - |
| `APSCHEDULER_ENABLED` | Habilitar avance automatico de niveles | `True` |
| `THROTTLE_ANON_RATE` | Rate limit anonimos | `30/minute` |
| `THROTTLE_USER_RATE` | Rate limit autenticados | `60/minute` |
| `THROTTLE_LOGIN_RATE` | Rate limit login | `5/minute` |

Para generar la `ENCRYPTION_KEY`:
```bash
python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

---

## Base de Datos

### Esquema Principal

El sistema utiliza las siguientes tablas (gestionadas por Django ORM):

- **users_user** - Usuarios del sistema (extiende AbstractUser)
- **users_studentprofile** - Perfil de estudiante (grupo asignado)
- **users_teacherprofile** - Perfil de profesor (departamento, materias)
- **users_passwordresetcode** - Codigos de recuperacion de contrasena
- **academic_generation** - Generaciones academicas
- **academic_period** - Periodos academicos
- **academic_group** - Grupos con nivel academico
- **academic_subject** - Materias por nivel
- **academic_unit** - Unidades tematicas
- **academic_groupteacherassignment** - Asignacion profesor-grupo-materia
- **questions_question** - Banco de preguntas
- **questions_answer** - Opciones de respuesta
- **questions_codequestion** - Datos adicionales para preguntas de codigo
- **exams_exam** - Configuracion de examenes
- **exams_examquestion** - Preguntas asignadas a examenes
- **exams_examassignment** - Asignacion examen-estudiante
- **exams_examgroupassignment** - Asignacion examen-grupo
- **answers_studentanswer** - Respuestas de estudiantes
- **audit_auditlog** - Registro de auditoria (gestionado por triggers PostgreSQL)

---

## Ejecutar el Proyecto

### Desarrollo

```bash
python3 manage.py runserver
```

El servidor estara disponible en: **http://127.0.0.1:8000**

### Verificar instalacion

- Health Check: http://127.0.0.1:8000/api/auth/health/
- Swagger UI: http://127.0.0.1:8000/api/docs/
- ReDoc: http://127.0.0.1:8000/api/redoc/

---

## Documentacion API

### Swagger UI (Interactivo)

Accede a **http://127.0.0.1:8000/api/docs/** para explorar y probar todos los endpoints.

### ReDoc (Referencia)

Accede a **http://127.0.0.1:8000/api/redoc/** para documentacion estatica.

### Schema OpenAPI

Descarga el schema en **http://127.0.0.1:8000/api/schema/**

---

## Endpoints

### Autenticacion (`/api/auth/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| POST | `/api/auth/login/` | Iniciar sesion | Publico |
| POST | `/api/auth/refresh/` | Refrescar token | Publico |
| POST | `/api/auth/change-password/` | Cambiar contrasena (payload cifrado) | Autenticado |
| GET | `/api/auth/health/` | Health check | Publico |

### Usuarios (`/api/users/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| GET | `/api/users/` | Listar usuarios (paginado, filtros) | Admin |
| POST | `/api/users/` | Crear usuario | Admin |
| GET | `/api/users/{id}/` | Detalle de usuario | Admin |
| PUT | `/api/users/{id}/` | Actualizar usuario | Admin |
| PATCH | `/api/users/{id}/status/` | Activar/desactivar usuario | Admin |
| GET | `/api/users/{id}/eligible-groups/` | Grupos elegibles para profesor | Admin |
| POST | `/api/users/password-recovery/request/` | Solicitar codigo de recuperacion | Publico |
| POST | `/api/users/password-recovery/verify/` | Verificar codigo | Publico |
| POST | `/api/users/password-recovery/reset/` | Restablecer contrasena | Publico |

### Academico (`/api/academic/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| GET/POST | `/api/academic/generations/` | Listar/crear generaciones | Admin |
| GET/PUT | `/api/academic/generations/{id}/` | Detalle/actualizar generacion | Admin |
| PATCH | `/api/academic/generations/{id}/status/` | Cambiar estado | Admin |
| GET/POST | `/api/academic/periods/` | Listar/crear periodos | Admin |
| GET | `/api/academic/periods/current/` | Periodo actual | Autenticado |
| POST | `/api/academic/periods/{id}/advance-groups/` | Avanzar niveles manualmente | Admin |
| GET/POST | `/api/academic/groups/` | Listar/crear grupos | Admin |
| GET | `/api/academic/groups/my-groups/` | Mis grupos (profesor) | Profesor |
| POST | `/api/academic/groups/{id}/assign-student/` | Asignar estudiante a grupo | Admin |
| GET/POST | `/api/academic/groups/{id}/assignments/` | Asignaciones profesor-materia | Admin |
| GET | `/api/academic/groups/{id}/students/` | Estudiantes del grupo | Profesor/Admin |
| GET/POST | `/api/academic/subjects/` | Listar/crear materias | Admin |
| GET | `/api/academic/subjects/my-subjects/` | Mis materias (profesor) | Profesor |
| GET | `/api/academic/subjects/{id}/units/` | Unidades de la materia | Autenticado |

### Preguntas (`/api/questions/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| GET | `/api/questions/` | Listar preguntas | Profesor/Admin |
| POST | `/api/questions/` | Crear pregunta | Profesor/Admin |
| GET | `/api/questions/{id}/` | Detalle de pregunta | Profesor/Admin |
| PUT | `/api/questions/{id}/` | Actualizar pregunta | Profesor/Admin |
| DELETE | `/api/questions/{id}/` | Eliminar pregunta | Profesor/Admin |

### Examenes (`/api/exams/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| GET/POST | `/api/exams/` | Listar/crear examenes | Profesor/Admin |
| GET/PUT | `/api/exams/{id}/` | Detalle/actualizar examen | Profesor/Admin |
| PATCH | `/api/exams/{id}/status/` | Cambiar estado (borrador/publicado) | Profesor/Admin |
| PATCH | `/api/exams/{id}/secure-mode/` | Activar/desactivar modo seguro | Profesor/Admin |
| DELETE | `/api/exams/{id}/delete/` | Eliminar examen (soft delete) | Profesor/Admin |
| GET/POST | `/api/exams/{id}/questions/` | Preguntas del examen | Profesor/Admin |
| POST | `/api/exams/exam-assignments/assign/` | Asignar examen a grupos | Profesor/Admin |
| GET | `/api/exams/exam-assignments/my-assignments/` | Mis examenes asignados | Estudiante |
| GET | `/api/exams/created-by-me/` | Examenes creados por mi | Profesor |
| GET | `/api/exams/{id}/stats/groups/` | Estadisticas por grupo | Profesor/Admin |
| GET | `/api/exams/{id}/stats/groups/{gid}/` | Estadisticas de un grupo | Profesor/Admin |
| GET | `/api/exams/{id}/groups/{gid}/students/` | Estudiantes del grupo en examen | Profesor/Admin |
| GET | `/api/exams/{id}/grades/.../export/excel/` | Exportar calificaciones Excel | Profesor/Admin |
| GET | `/api/exams/{id}/grades/.../export/pdf/` | Exportar calificaciones PDF | Profesor/Admin |
| GET | `/api/exams/template/download/` | Descargar plantilla de importacion | Profesor/Admin |

### Respuestas (`/api/answers/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| POST | `/api/answers/submit/` | Enviar respuestas de examen | Estudiante |
| POST | `/api/answers/forfeit/` | Abandonar examen | Estudiante |
| POST | `/api/answers/manual-grade/` | Calificar manualmente | Profesor |
| GET | `/api/answers/assignment/{id}/` | Ver respuestas de asignacion | Profesor/Admin |

### Reportes (`/api/reports/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| POST | `/api/reports/by-exam/` | Reporte por examen | Profesor/Admin |
| POST | `/api/reports/by-group/` | Reporte por grupo | Profesor/Admin |
| POST | `/api/reports/by-student/` | Reporte por estudiante | Profesor/Admin |
| POST | `/api/reports/student-exam-detail/` | Detalle estudiante-examen | Profesor/Admin |

### Auditoria (`/api/audit-logs/`)

| Metodo | Ruta | Descripcion | Acceso |
|---|---|---|---|
| GET | `/api/audit-logs/` | Listar logs de auditoria | Admin |

---

## Roles de Usuario

| Rol | Descripcion |
|---|---|
| **admin** | Acceso completo: gestion de usuarios, configuracion academica, reportes, auditoria |
| **teacher** | Crear examenes, gestionar banco de preguntas, asignar examenes, calificar, ver reportes |
| **student** | Ver examenes asignados, responder examenes, ver calificaciones propias |

---

## Avance Automatico de Niveles Academicos

APScheduler ejecuta el avance de niveles al inicio de cada periodo:

- **1 de enero** (Enero-Abril)
- **1 de mayo** (Mayo-Agosto)
- **1 de septiembre** (Septiembre-Diciembre)

Formula:
```
academic_level = ((year_actual - year_generacion) * 3) + (indice_periodo_actual - indice_periodo_inicio) + 1
```

### Configuracion

```env
APSCHEDULER_ENABLED=True   # Habilitar (por defecto)
APSCHEDULER_ENABLED=False  # Deshabilitar
```

### Ejecucion manual

```bash
python manage.py advance_academic_levels           # Ejecutar
python manage.py advance_academic_levels --dry-run  # Simular sin cambios
```

### Monitoreo

Logs en `logs/info.log` y `logs/error.log`.

---

## Despliegue

### Docker (desarrollo local)

```bash
docker-compose up -d    # Inicia PostgreSQL
python3 manage.py migrate
python3 manage.py runserver
```

### Render (produccion)

El proyecto incluye `render.yaml` con la configuracion necesaria:

- **Build**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Start**: `python manage.py migrate && gunicorn config.wsgi`
- **Base de datos**: PostgreSQL externo (Supabase)
- **Archivos estaticos**: Servidos con WhiteNoise

---

## Comandos Utiles

```bash
python3 manage.py makemigrations       # Crear migraciones
python3 manage.py migrate              # Aplicar migraciones
python3 manage.py createsuperuser      # Crear superusuario
python3 manage.py shell                # Shell interactivo
python3 manage.py collectstatic        # Recolectar archivos estaticos
```

---

## Solucion de Problemas

### Error de conexion a PostgreSQL

```bash
# Verificar que PostgreSQL esta corriendo
psql -U postgres -c "SELECT 1"

# O con Docker
docker-compose ps
```

### Error de migraciones

```bash
python3 manage.py migrate
```

### Problemas con CORS

Verificar que `CORS_ALLOWED_ORIGINS` incluya el origen del frontend en `.env`.

### Emails no se envian

Verificar que `BREVO_API_KEY` este configurado correctamente en `.env`.

---

## Probar con cURL

### Login
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@legacydevs.com", "password": "1234"}'
```

### Peticion autenticada
```bash
curl -X GET http://127.0.0.1:8000/api/users/ \
  -H "Authorization: Bearer <TU_ACCESS_TOKEN>"
```

---

Desarrollado por Legacy Devs

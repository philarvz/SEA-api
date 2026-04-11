# SEA-API - Sistema de Evaluación Académica

API REST para la gestión de exámenes y evaluaciones académicas construida con Django REST Framework y PostgreSQL.

---

## 📋 Tabla de Contenidos

- [Características](#características)
- [Tecnologías](#tecnologías)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Configuración Inicial](#configuración-inicial)
- [Base de Datos](#base-de-datos)
- [Usuario Administrador](#usuario-administrador)
- [Ejecutar el Proyecto](#ejecutar-el-proyecto)
- [Documentación API](#documentación-api)
- [Endpoints Principales](#endpoints-principales)

---

## ✨ Características

- 🔐 Autenticación JWT (JSON Web Tokens)
- 👥 Gestión de usuarios (Estudiantes, Profesores, Administradores)
- 📚 Gestión de materias y unidades académicas
- 📝 Sistema de preguntas y respuestas
- 📋 Creación y asignación de exámenes
- 🎯 Seguimiento de calificaciones
- 📖 Documentación interactiva con Swagger

---

## 🛠️ Tecnologías

- **Python 3.9+**
- **Django 4.2**
- **Django REST Framework 3.16**
- **PostgreSQL** (Base de datos)
- **JWT** (Autenticación)
- **Swagger/OpenAPI** (Documentación)

---

## 📁 Estructura del Proyecto

```
integradora/
├── apps/
│   ├── authentication/      # Autenticación y tokens JWT
│   ├── users/              # Modelos Person y UserAccount
│   ├── academic/           # Términos, grupos, materias, unidades
│   ├── questions/          # Preguntas y respuestas
│   ├── exams/             # Exámenes y asignaciones
│   └── core/              # Utilidades core
├── config/
│   ├── settings.py        # Configuración del proyecto
│   └── urls.py           # URLs principales
├── utils/                # Utilidades generales
├── manage.py            # CLI de Django
├── requirements.txt     # Dependencias
└── .env                # Variables de entorno
```

---

## ⚙️ Configuración Inicial

### 1. Clonar el Repositorio

```bash
git clone <url-del-repositorio>
cd integradora
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

Edita el archivo `.env` con tus credenciales de PostgreSQL:

```env
# Django
SECRET_KEY=django-insecure-sea-api-development-key-2026
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# JWT
JWT_SECRET_KEY=legacydevs
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# Database
USE_DATABASE=True
DB_NAME=SEA_database
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_HOST=localhost
DB_PORT=5432
```

---

## 🗄️ Base de Datos

### Esquema de Base de Datos

El sistema utiliza 11 tablas principales:

- **person** - Información de personas (estudiantes, profesores, admins)
- **user_account** - Cuentas de usuario (1:1 con person)
- **generation** - Generaciones académicas por año
- **period** - Periodos académicos (Enero-Abril, Mayo-Agosto, Septiembre-Diciembre)
- **group** - Grupos de estudiantes (con academic_level)
- **subject** - Materias (con academic_level)
- **unit** - Unidades temáticas
- **question** - Preguntas de exámenes
- **answer** - Respuestas de preguntas
- **exam** - Exámenes
- **exam_question** - Relación examen-pregunta
- **exam_person** - Asignación de exámenes a estudiantes

### Crear Base de Datos

Si usas PostgreSQL localmente, crea la base de datos:

```bash
# Acceder a PostgreSQL
psql -U postgres

# Crear base de datos
CREATE DATABASE SEA_database;
\q
```

### Ejecutar el Script SQL

```bash
psql -U postgres -d SEA_database -f init.sql
```

Este script:
- ✅ Crea todas las tablas del sistema
- ✅ Define relaciones y constraints
- ✅ Crea el usuario administrador inicial

---

## 👤 Usuario Administrador

### Creación Automática

Al ejecutar el script `init.sql`, se crea automáticamente un usuario administrador:

**Credenciales:**
- **Email**: `admin@legacydevs.com`
- **Username**: `admin`
- **Password**: `1234`
- **Role**: `admin`

### Crear/Actualizar Manualmente

Si necesitas recrear o actualizar el usuario admin:

```bash
python3 create_admin.py
```

Este script:
- Crea un usuario admin si no existe
- Actualiza la contraseña si ya existe
- Usa hashing de Django para seguridad

### Crear Usuarios de Prueba

```bash
python3 create_test_users.py
```

Esto crea usuarios adicionales:
- **Estudiante**: juan.perez@example.com / test123
- **Profesor**: maria.garcia@example.com / test123

---

## 🚀 Ejecutar el Proyecto

### Iniciar el Servidor

```bash
python3 manage.py runserver
```

El servidor estará disponible en: **http://127.0.0.1:8000**

### Verificar Instalación

Accede a:
- API Health: http://127.0.0.1:8000/api/auth/health/
- Swagger UI: http://127.0.0.1:8000/api/docs/
- ReDoc: http://127.0.0.1:8000/api/redoc/

---

## � Gestión de Periodos Académicos

### Periodos Automáticos

El sistema maneja **tres periodos académicos fijos** por año:

- **Enero-Abril**: 1 de enero al 30 de abril
- **Mayo-Agosto**: 1 de mayo al 31 de agosto
- **Septiembre-Diciembre**: 1 de septiembre al 31 de diciembre

Las fechas se calculan automáticamente. Solo necesitas registrar el **año** y el **nombre del periodo**.

### Generar Periodos

Usa el script helper para crear periodos de múltiples años:

```bash
# Generar periodos para un año específico
python scripts/generate_periods.py --year 2025

# Generar periodos para un rango de años
python scripts/generate_periods.py --start-year 2024 --end-year 2026
```

Este script crea automáticamente los tres periodos para cada año, sin necesidad de ingresar fechas manualmente.

### Avance Automático de Niveles Académicos

El sistema incrementa automáticamente el nivel académico (`academic_level`) de todos los grupos al inicio de cada periodo mediante un **management command programado**:

```bash
# Ejecutar manualmente (producción)
python manage.py advance_academic_levels

# Probar sin hacer cambios (dry-run)
python manage.py advance_academic_levels --dry-run
```

#### Configurar Ejecución Automática

**En Linux (Cron):**

Edita el crontab:
```bash
crontab -e
```

Agrega las siguientes líneas para ejecutar automáticamente a las 12:00 AM del 1 de enero, mayo y septiembre:
```cron
0 0 1 1 * /ruta/al/entorno/python /ruta/al/proyecto/manage.py advance_academic_levels
0 0 1 5 * /ruta/al/entorno/python /ruta/al/proyecto/manage.py advance_academic_levels
0 0 1 9 * /ruta/al/entorno/python /ruta/al/proyecto/manage.py advance_academic_levels
```

**En Windows (Task Scheduler):**

1. Abre **Programador de tareas** (Task Scheduler)
2. Crea tres tareas programadas:
   - **Nombre**: `SEA_Advance_January`
   - **Desencadenador**: 1 de enero a las 00:00, repetir cada año
   - **Acción**: Ejecutar programa
     - Programa: `C:\Python39\python.exe` (ruta a tu Python)
     - Argumentos: `manage.py advance_academic_levels`
     - Iniciar en: `C:\ruta\al\proyecto\SEA-api`
   
3. Repite para mayo (5/1) y septiembre (9/1)

#### Funcionamiento

El comando:
- Detecta el periodo actual basado en la fecha de ejecución
- Calcula el nuevo nivel académico de cada grupo usando la fórmula:
  ```
  academic_level = ((año_actual - año_generación) * 3) + (índice_periodo_actual - índice_periodo_inicio) + 1
  ```
- Actualiza el nivel de cada grupo, respetando el límite `total_levels` de su generación
- Registra todos los cambios en los logs

> **Nota**: El comando valida que se ejecute en el primer día de un periodo (1/ene, 1/may, 1/sep) y emite una advertencia si no es así.

---

## �� Documentación API

### Swagger UI (Interactivo)

Accede a **http://127.0.0.1:8000/api/docs/** para:
- Ver todos los endpoints disponibles
- Probar peticiones directamente desde el navegador
- Ver esquemas de request/response
- Autenticarte con JWT tokens

### ReDoc (Estático)

Accede a **http://127.0.0.1:8000/api/redoc/** para documentación estática.

---

## 🔌 Endpoints Principales

### Autenticación

#### Login
```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "admin@legacydevs.com",
  "password": "1234"
}
```

**Respuesta:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@legacydevs.com",
    "first_name": "Admin",
    "last_name": "LegacyDevs",
    "full_name": "Admin LegacyDevs",
    "role": "admin"
  }
}
```

#### Refresh Token
```http
POST /api/auth/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

#### Health Check
```http
GET /api/auth/health/
```

### Usar JWT en Peticiones Protegidas

Agrega el token de acceso en el header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## 🧪 Probar con cURL

### Login
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@legacydevs.com",
    "password": "1234"
  }'
```

### Con Token
```bash
curl -X GET http://127.0.0.1:8000/api/endpoint-protegido/ \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

---

## 📝 Comandos Útiles

```bash
# Crear migraciones (si modificas modelos)
python3 manage.py makemigrations

# Aplicar migraciones
python3 manage.py migrate

# Crear superusuario Django (opcional)
python3 manage.py createsuperuser

# Acceder a shell interactivo
python3 manage.py shell

# Ver todas las rutas
python3 manage.py show_urls
```

---

## 🔒 Seguridad

- Las contraseñas se almacenan hasheadas con PBKDF2-SHA256
- Autenticación basada en JWT tokens
- CORS configurado para desarrollo (ajustar en producción)
- Variables sensibles en archivo `.env`

---

## 📊 Roles de Usuario

El sistema soporta 3 roles:

- **admin** - Acceso completo al sistema
- **teacher** - Crear y gestionar exámenes
- **student** - Tomar exámenes asignados

---

## 🐛 Solución de Problemas

### Error de Conexión a PostgreSQL

Verifica que PostgreSQL esté corriendo:
```bash
psql -U postgres -c "SELECT 1"
```

### Error de Migraciones

Aplica las migraciones:
```bash
python3 manage.py migrate
```

### Usuario Admin No Funciona

Recrea el usuario admin:
```bash
python3 create_admin.py
```

---

## 📞 Soporte

Para dudas o problemas:
- Email: admin@legacydevs.com
- Documentación: http://127.0.0.1:8000/api/docs/

---

Desarrollado con ❤️ por Legacy Devs

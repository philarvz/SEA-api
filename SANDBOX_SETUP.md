# Guía de Configuración del Sandbox — SEA-API

## ¿Qué es el Sandbox?

El sandbox es un contenedor Docker aislado que ejecuta el código Python de los estudiantes de forma **segura**. Cuando un alumno envía una respuesta de tipo CODE, el backend crea un contenedor efímero, ejecuta el código dentro, y lo destruye inmediatamente.

**Sin el sandbox construido, las preguntas de tipo CODE no funcionarán.**

---

## Requisitos Previos

| Requisito | Versión mínima | Verificar con |
|-----------|---------------|---------------|
| Docker Desktop | 4.x | `docker --version` |
| Python | 3.9+ | `python --version` |
| Git | cualquiera | `git --version` |

> **Docker Desktop debe estar corriendo** antes de construir la imagen o ejecutar el backend.

---

## Configuración en cada computadora (desarrollo)

### Paso 1 — Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd SEA-api
```

### Paso 2 — Construir la imagen del sandbox

```bash
docker build -t sea-sandbox:latest ./sandbox
```

Este comando:
- Lee el archivo `sandbox/Dockerfile`
- Crea una imagen Python 3.11-slim con el script `runner.py`
- La etiqueta como `sea-sandbox:latest`

**Tiempo estimado:** ~30 segundos la primera vez, ~5 segundos después (caché).

### Paso 3 — Verificar que la imagen existe

```bash
docker image ls sea-sandbox
```

Debe mostrar algo como:

```
REPOSITORY    TAG       IMAGE ID       CREATED         SIZE
sea-sandbox   latest    e8ad187746fe   2 minutes ago   186MB
```

### Paso 4 — Verificar que funciona

```bash
echo {"code":"def suma(a,b): return a+b","test_cases":[{"function_name":"suma","input":[2,3],"expected_output":5}]} | docker run --rm -i sea-sandbox:latest
```

**En PowerShell** el comando anterior puede fallar por caracteres especiales. Usa este script Python en su lugar:

```python
# test_sandbox.py
import json, subprocess

payload = json.dumps({
    "code": "def suma(a, b): return a + b",
    "test_cases": [
        {"function_name": "suma", "input": [2, 3], "expected_output": 5}
    ]
})

result = subprocess.run(
    ["docker", "run", "--rm", "--network", "none", "-i", "sea-sandbox:latest"],
    input=payload, capture_output=True, text=True, timeout=10
)
print(result.stdout)
```

```bash
python test_sandbox.py
```

Resultado esperado:

```json
{"passed": true, "results": [{"input": [2, 3], "expected": 5, "output": 5, "passed": true}], "error": null}
```

### Paso 5 — Levantar la base de datos y el backend

```bash
# Levantar PostgreSQL
docker compose up -d postgres

# Instalar dependencias Python
pip install -r requirements.txt

# Migraciones
python manage.py migrate

# Ejecutar el servidor
python manage.py runserver
```

---

## Variables de entorno opcionales (`.env`)

El sandbox funciona con valores por defecto, pero se pueden personalizar:

```env
# Imagen Docker a usar para el sandbox
SANDBOX_DOCKER_IMAGE=sea-sandbox:latest

# Tiempo máximo de ejecución en segundos (default: 5)
SANDBOX_TIMEOUT_SECONDS=5

# Límite de memoria del contenedor (default: 128m)
SANDBOX_MEMORY_LIMIT=128m

# Límite de CPU (default: 0.5 = medio core)
SANDBOX_CPU_LIMIT=0.5

# Límite de procesos dentro del contenedor (default: 64)
SANDBOX_PIDS_LIMIT=64
```

---

## Consideraciones para despliegue (producción/servidor)

### 1. Docker debe estar instalado en el servidor

El proceso Django llama a `docker run` directamente mediante `subprocess`. Si Docker no está en el servidor, las preguntas CODE fallarán con el error:

```
"Error interno: el entorno de ejecucion no esta disponible."
```

### 2. Construir la imagen en el servidor

Después de clonar o actualizar el código en el servidor:

```bash
docker build -t sea-sandbox:latest ./sandbox
```

**Esto debe ejecutarse cada vez que se modifique `sandbox/runner.py` o `sandbox/Dockerfile`.**

### 3. Permisos de Docker

El usuario del sistema que ejecuta Django debe tener permisos para ejecutar `docker run`. Opciones:

```bash
# Opción A: agregar el usuario al grupo docker
sudo usermod -aG docker $USER

# Opción B: si usan systemd, verificar que Docker esté activo
sudo systemctl enable docker
sudo systemctl start docker
```

### 4. Seguridad — Flags aplicados automáticamente

Cada contenedor se ejecuta con estas restricciones (no hay que configurar nada, el código las aplica):

| Flag | Efecto |
|------|--------|
| `--rm` | El contenedor se elimina al terminar |
| `--network none` | Sin acceso a internet |
| `--memory 128m` | Límite de RAM (mata el proceso si se excede) |
| `--cpus 0.5` | Máximo medio core de CPU |
| `--read-only` | Sistema de archivos inmutable |
| `--pids-limit 64` | Protección contra fork bombs |
| `USER sandbox` | No corre como root dentro del contenedor |

### 5. Recursos del servidor

Cada ejecución de código crea un contenedor efímero que vive máximo 5 segundos. Considerar:

- **RAM:** cada contenedor usa máximo 128 MB. Si hay 10 alumnos enviando código simultáneamente = ~1.3 GB.
- **CPU:** cada contenedor usa máximo 0.5 cores. Con 10 simultáneos = 5 cores.
- **Disco:** los contenedores son efímeros (`--rm`), no dejan datos en disco.

### 6. Si usan Docker Compose para todo el deploy

```bash
# Construir la imagen del sandbox (una sola vez o al actualizar)
docker compose build sandbox

# Levantar solo PostgreSQL
docker compose up -d postgres
```

El sandbox NO se levanta como servicio — solo se construye la imagen para que Django la use vía `docker run`.

---

## Resumen rápido — Checklist por computadora

- [ ] Docker Desktop instalado y corriendo
- [ ] Ejecutar `docker build -t sea-sandbox:latest ./sandbox`
- [ ] Verificar con `docker image ls sea-sandbox`
- [ ] Archivo `.env` configurado con las variables de BD
- [ ] `pip install -r requirements.txt`
- [ ] `python manage.py migrate`
- [ ] `python manage.py runserver`

---

## Solución de problemas

| Error | Causa | Solución |
|-------|-------|----------|
| `"Error interno: el entorno de ejecucion no esta disponible."` | Docker no está instalado o no está corriendo | Iniciar Docker Desktop |
| `"El codigo excedio el tiempo limite..."` | Bucle infinito o código muy lento del alumno | El código del alumno tiene un error, no es problema del sistema |
| `"El codigo excedio el limite de memoria permitido."` | El código usa demasiada memoria | Igual, error del alumno |
| `"Error de ejecucion en el entorno aislado."` | Error de sintaxis o runtime en el código del alumno | Normal, se reporta al alumno |
| La imagen no se encuentra | No se construyó la imagen | Ejecutar `docker build -t sea-sandbox:latest ./sandbox` |

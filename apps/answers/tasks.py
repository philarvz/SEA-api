"""
Celery task that executes untrusted student code inside an isolated Docker
container.

Flow
----
1. Celery worker picks up the task.
2. A JSON payload (code + test_cases) is piped to ``docker run`` via stdin.
3. The container runs ``sandbox/runner.py``, writes JSON to stdout, then exits.
4. The task captures stdout/stderr in the host, enforces a hard timeout, and
   returns structured results to the caller.

Security controls applied at *run-time*:
  • ``--rm``            → container is deleted immediately after exit.
  • ``--network none``  → no network access whatsoever.
  • ``--memory 128m``   → hard memory cap; OOM-killer fires on abuse.
  • ``--cpus 0.5``      → limited CPU slicing.
  • ``--read-only``     → root filesystem is immutable.
  • ``--pids-limit 64`` → fork-bomb protection.
  • ``--user sandbox``  → non-root inside the container (set in Dockerfile).
  • subprocess timeout  → kills the whole process tree if exceeded.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from celery import shared_task
from django.conf import settings
from loguru import logger


# Default limits — overridable via Django settings / env vars.
_SANDBOX_IMAGE = getattr(settings, 'SANDBOX_DOCKER_IMAGE', 'sea-sandbox:latest')
_SANDBOX_TIMEOUT = int(getattr(settings, 'SANDBOX_TIMEOUT_SECONDS', 10))
_SANDBOX_MEMORY = getattr(settings, 'SANDBOX_MEMORY_LIMIT', '128m')
_SANDBOX_CPUS = getattr(settings, 'SANDBOX_CPU_LIMIT', '0.5')
_SANDBOX_PIDS = getattr(settings, 'SANDBOX_PIDS_LIMIT', '64')


def _build_docker_command() -> list[str]:
    """Return the ``docker run`` argument list with all security flags."""
    return [
        'docker', 'run',
        '--rm',                          # Ephemeral: delete container after exit
        '--network', 'none',             # No network access
        '--memory', _SANDBOX_MEMORY,     # Hard memory limit
        '--cpus', _SANDBOX_CPUS,         # CPU throttle
        '--read-only',                   # Immutable root filesystem
        '--pids-limit', _SANDBOX_PIDS,   # Fork-bomb protection
        '-i',                            # Keep stdin open to pipe JSON
        _SANDBOX_IMAGE,
    ]


@shared_task(
    bind=True,
    name='answers.run_code_in_sandbox',
    max_retries=0,                       # Student code is deterministic — no retries
    acks_late=False,
    time_limit=_SANDBOX_TIMEOUT + 10,    # Hard Celery kill (container + overhead)
    soft_time_limit=_SANDBOX_TIMEOUT + 5,
)
def run_code_in_sandbox(
    self,
    code: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute *code* against *test_cases* inside a Docker sandbox.

    Returns a dict with keys ``passed``, ``results``, ``error``.
    """
    payload = json.dumps({'code': code, 'test_cases': test_cases})
    cmd = _build_docker_command()

    logger.info(
        'Sandbox task started | task_id={} tests={}',
        self.request.id,
        len(test_cases),
    )

    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=_SANDBOX_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        logger.warning('Sandbox timeout | task_id={}', self.request.id)
        return {
            'passed': False,
            'results': [],
            'error': (
                'El codigo excedio el tiempo limite de ejecucion '
                f'({_SANDBOX_TIMEOUT}s). Posible bucle infinito.'
            ),
        }
    except FileNotFoundError:
        logger.error('Docker binary not found on worker')
        return {
            'passed': False,
            'results': [],
            'error': 'Error interno: el entorno de ejecucion no esta disponible.',
        }
    except Exception as exc:
        logger.error('Sandbox unexpected error | task_id={} exc={}', self.request.id, exc)
        return {
            'passed': False,
            'results': [],
            'error': 'Error interno al ejecutar el codigo.',
        }

    # Non-zero exit: container crashed or OOM-killed.
    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or '')[:500]
        logger.warning(
            'Sandbox non-zero exit | task_id={} rc={} stderr={}',
            self.request.id,
            proc.returncode,
            stderr_snippet,
        )
        # Exit code 137 = SIGKILL (typically OOM).
        if proc.returncode == 137:
            return {
                'passed': False,
                'results': [],
                'error': 'El codigo excedio el limite de memoria permitido.',
            }
        return {
            'passed': False,
            'results': [],
            'error': 'Error de ejecucion en el entorno aislado.',
        }

    # Parse JSON from the runner.
    stdout = proc.stdout.strip()
    if not stdout:
        return {
            'passed': False,
            'results': [],
            'error': 'El entorno de ejecucion no produjo resultados.',
        }

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error('Sandbox invalid JSON | task_id={} raw={}', self.request.id, stdout[:300])
        return {
            'passed': False,
            'results': [],
            'error': 'Error interno: resultado de ejecucion corrupto.',
        }

    logger.info(
        'Sandbox task finished | task_id={} passed={}',
        self.request.id,
        result.get('passed'),
    )
    return result

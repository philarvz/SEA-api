"""
Synchronous Docker sandbox execution for student code.

Replaces the previous Celery-based async flow.  Student code is executed
inside an ephemeral Docker container via ``subprocess.run`` and results
are returned directly to the caller — no broker or worker required.

Security controls (identical to the former Celery task):
  • ``--rm``            → container deleted immediately after exit.
  • ``--network none``  → zero network access.
  • ``--memory``        → hard memory cap (OOM-kill on abuse).
  • ``--cpus``          → CPU throttle.
  • ``--read-only``     → immutable root filesystem.
  • ``--pids-limit``    → fork-bomb protection.
  • Non-root user inside the container (set in Dockerfile).
  • ``subprocess`` timeout → kills the process tree if exceeded.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from django.conf import settings
from loguru import logger

# ---------------------------------------------------------------------------
# Sandbox limits — read once from Django settings (backed by env vars).
# ---------------------------------------------------------------------------
_IMAGE: str = getattr(settings, 'SANDBOX_DOCKER_IMAGE', 'sea-sandbox:latest')
_TIMEOUT: int = int(getattr(settings, 'SANDBOX_TIMEOUT_SECONDS', 5))
_MEMORY: str = getattr(settings, 'SANDBOX_MEMORY_LIMIT', '128m')
_CPUS: str = getattr(settings, 'SANDBOX_CPU_LIMIT', '0.5')
_PIDS: str = getattr(settings, 'SANDBOX_PIDS_LIMIT', '64')

# Pre-built command list — every element is a safe literal, never user input.
_DOCKER_CMD: list[str] = [
    'docker', 'run',
    '--rm',                    # Ephemeral container
    '--network', 'none',       # No network
    '--memory', _MEMORY,       # Memory cap
    '--cpus', _CPUS,           # CPU cap
    '--read-only',             # Immutable FS
    '--pids-limit', _PIDS,     # Fork-bomb guard
    '-i',                      # Accept stdin
    _IMAGE,
]


def run_code_in_sandbox(
    code: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute *code* against *test_cases* inside a Docker sandbox.

    The function is **synchronous** — it blocks until the container exits
    or the timeout fires, then returns a structured result dict::

        {
            "passed": bool,
            "results": [ {"input": …, "expected": …, "output": …, "passed": bool}, … ],
            "error": str | None,
        }
    """
    payload = json.dumps({'code': code, 'test_cases': test_cases})

    try:
        proc = subprocess.run(
            _DOCKER_CMD,
            input=payload,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning('Sandbox timeout after {}s', _TIMEOUT)
        return {
            'passed': False,
            'results': [],
            'error': (
                f'El codigo excedio el tiempo limite de ejecucion '
                f'({_TIMEOUT}s). Posible bucle infinito.'
            ),
        }
    except FileNotFoundError:
        logger.error('Docker binary not found — is Docker installed?')
        return {
            'passed': False,
            'results': [],
            'error': 'Error interno: el entorno de ejecucion no esta disponible.',
        }
    except Exception as exc:
        logger.error('Sandbox unexpected error | {}', exc)
        return {
            'passed': False,
            'results': [],
            'error': 'Error interno al ejecutar el codigo.',
        }

    # --- Non-zero exit ------------------------------------------------
    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or '')[:500]
        logger.warning('Sandbox exit code {} | stderr: {}', proc.returncode, stderr_snippet)

        if proc.returncode == 137:          # SIGKILL — typically OOM
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

    # --- Parse JSON output --------------------------------------------
    stdout = proc.stdout.strip()
    if not stdout:
        return {
            'passed': False,
            'results': [],
            'error': 'El entorno de ejecucion no produjo resultados.',
        }

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        logger.error('Sandbox returned invalid JSON | raw={}', stdout[:300])
        return {
            'passed': False,
            'results': [],
            'error': 'Resultado invalido del sandbox.',
        }

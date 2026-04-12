"""
runner.py — Executes student code inside the sandbox container.

Protocol
--------
• INPUT  (stdin):  JSON object
    {
        "code": "<student source code>",
        "test_cases": [
            {"function_name": "suma", "input": [2, 3], "expected_output": 5},
            ...
        ]
    }

• OUTPUT (stdout): JSON object
    {
        "passed": true | false,
        "results": [
            {"input": ..., "expected": ..., "output": ..., "passed": true | false}
        ],
        "error": null | "<message>"
    }

Security notes
--------------
This script is the ONLY Python that runs inside the ephemeral container.
The container itself enforces:
  - --network none (no internet)
  - --memory 128m   (OOM-kill on abuse)
  - --cpus 0.5      (throttled CPU)
  - --read-only      (immutable root FS)
  - timeout enforced by the caller via subprocess

Even so, we restrict __builtins__ to a safe subset so that
`import os` / `open()` / `eval()` etc. are not available to students.
"""

import json
import sys
import traceback

# ---------------------------------------------------------------
# Whitelist of safe built-in names available to student code.
# Anything NOT listed here is hidden (import, open, exec …).
# ---------------------------------------------------------------
_SAFE_BUILTINS = {
    'abs': abs,
    'all': all,
    'any': any,
    'bool': bool,
    'chr': chr,
    'dict': dict,
    'divmod': divmod,
    'enumerate': enumerate,
    'filter': filter,
    'float': float,
    'frozenset': frozenset,
    'hasattr': hasattr,
    'hash': hash,
    'int': int,
    'isinstance': isinstance,
    'issubclass': issubclass,
    'iter': iter,
    'len': len,
    'list': list,
    'map': map,
    'max': max,
    'min': min,
    'next': next,
    'ord': ord,
    'pow': pow,
    'print': print,
    'range': range,
    'repr': repr,
    'reversed': reversed,
    'round': round,
    'set': set,
    'slice': slice,
    'sorted': sorted,
    'str': str,
    'sum': sum,
    'tuple': tuple,
    'type': type,
    'zip': zip,
    'True': True,
    'False': False,
    'None': None,
    "__import__": None
}


def _execute_code(code: str, namespace: dict) -> str | None:
    """Compile and execute *code* inside *namespace*.

    Returns an error string on failure, ``None`` on success.
    """
    try:
        compiled = compile(code, '<student_code>', 'exec')
        exec(compiled, namespace)  # noqa: S102 — intentional; sandboxed by Docker
        return None
    except Exception:
        return traceback.format_exc()


def _call_function(fn, raw_input):
    """Invoke *fn* with the given input (list ⇒ *args, dict ⇒ **kwargs, else single arg)."""
    if isinstance(raw_input, list):
        return fn(*raw_input)
    if isinstance(raw_input, dict):
        return fn(**raw_input)
    return fn(raw_input)


def _run_test_case(test_case, namespace: dict) -> dict:
    """Run a single test case and return a result dict.

    Supports two formats:
      • **dict** — ``{"function_name": "f", "input": [...], "expected_output": ...}``
      • **str**  — raw assertion, e.g. ``'assert f(2, 3) == 5'``
    """
    # --- String-style assertion (e.g. stored as 'assert func(...) == value') ---
    if isinstance(test_case, str):
        try:
            compiled = compile(test_case, '<test_case>', 'exec')
            exec(compiled, namespace)  # noqa: S102 — sandboxed by Docker
            return {'input': test_case, 'expected': 'pass', 'output': 'pass', 'passed': True}
        except AssertionError:
            return {'input': test_case, 'expected': 'pass', 'output': 'fail', 'passed': False, 'error': 'Assertion failed'}
        except Exception:
            return {'input': test_case, 'expected': 'pass', 'output': None, 'passed': False, 'error': traceback.format_exc()}

    # --- Dict-style test case (function_name + input + expected_output) ---
    fn_name = test_case.get('function_name', '')
    raw_input = test_case.get('input')
    expected = test_case.get('expected_output')

    fn = namespace.get(fn_name)
    if fn is None or not callable(fn):
        return {
            'input': raw_input,
            'expected': expected,
            'output': None,
            'passed': False,
            'error': f'La funcion "{fn_name}" no esta definida o no es invocable.',
        }

    try:
        output = _call_function(fn, raw_input)
    except Exception:
        return {
            'input': raw_input,
            'expected': expected,
            'output': None,
            'passed': False,
            'error': traceback.format_exc(),
        }

    passed = output == expected
    return {
        'input': raw_input,
        'expected': expected,
        'output': output,
        'passed': passed,
    }


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        json.dump({'passed': False, 'results': [], 'error': f'JSON invalido: {exc}'}, sys.stdout)
        return

    code = payload.get('code', '')
    test_cases = payload.get('test_cases', [])

    # Restricted namespace — student code cannot import modules or open files.
    namespace: dict = {'__builtins__': _SAFE_BUILTINS}

    compile_error = _execute_code(code, namespace)
    if compile_error:
        json.dump({'passed': False, 'results': [], 'error': compile_error}, sys.stdout)
        return

    results = [_run_test_case(tc, namespace) for tc in test_cases]
    all_passed = all(r['passed'] for r in results)

    json.dump({'passed': all_passed, 'results': results, 'error': None}, sys.stdout)


if __name__ == '__main__':
    main()

"""
Centralized input sanitization utilities for the SEA-API project.
Prevents XSS, injection attacks, and enforces length/format constraints.
"""

import re
import html
from typing import Optional

# Maximum lengths for common field types
MAX_NAME_LENGTH = 150
MAX_EMAIL_LENGTH = 254
MAX_SEARCH_LENGTH = 200
MAX_STATEMENT_LENGTH = 5000
MAX_ANSWER_TEXT_LENGTH = 1000
MAX_URL_LENGTH = 500
MAX_CODE_LENGTH = 10000
MAX_TEST_CASE_LENGTH = 5000

# Patterns
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_SCRIPT_RE = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
_EVENT_HANDLER_RE = re.compile(r'\bon\w+\s*=', re.IGNORECASE)

# Dangerous Python keywords/modules for code sandbox
DANGEROUS_KEYWORDS = frozenset({
    '__import__', 'import', 'exec', 'eval', 'compile',
    'globals', 'locals', 'vars', 'dir', 'getattr', 'setattr',
    'delattr', 'hasattr', '__builtins__', '__class__',
    '__subclasses__', '__bases__', '__mro__',
    'breakpoint', '__loader__', '__spec__',
})

DANGEROUS_MODULES = frozenset({
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'http',
    'urllib', 'requests', 'ctypes', 'signal', 'threading',
    'multiprocessing', 'pickle', 'shelve', 'marshal',
    'importlib', 'pkgutil', 'code', 'codeop', 'compileall',
    'asyncio', 'concurrent', 'webbrowser', 'pathlib',
    'tempfile', 'glob', 'fnmatch', 'io', 'builtins',
})


def strip_html_tags(value: str) -> str:
    """Remove all HTML tags from a string."""
    return _HTML_TAG_RE.sub('', value)


def sanitize_text(value: Optional[str], max_length: int = MAX_NAME_LENGTH) -> str:
    """
    Sanitize a text input: strip whitespace, remove HTML tags,
    escape remaining HTML entities, enforce max length.
    """
    if not value:
        return ''
    value = str(value).strip()
    value = _SCRIPT_RE.sub('', value)
    value = strip_html_tags(value)
    value = html.escape(value, quote=True)
    return value[:max_length]


def sanitize_name(value: Optional[str], max_length: int = MAX_NAME_LENGTH) -> str:
    """
    Sanitize a person name: only allows letters, spaces, hyphens, apostrophes, periods.
    Does NOT strip HTML tags — callers must reject HTML before calling this.
    """
    if not value:
        return ''
    value = str(value).strip()
    # Allow unicode letters, spaces, hyphens, apostrophes, periods
    value = re.sub(r"[^\w\s\-'.áéíóúÁÉÍÓÚñÑüÜ]", '', value, flags=re.UNICODE)
    return value[:max_length]


def contains_html(value: str) -> bool:
    """Check if a string contains HTML tags or event handlers."""
    if not value:
        return False
    return bool(_HTML_TAG_RE.search(value) or _EVENT_HANDLER_RE.search(value))


def validate_no_html(value: str, field_name: str = 'campo') -> None:
    """Raise ValueError if the value contains HTML/script content."""
    if contains_html(value):
        raise ValueError(f'El {field_name} no debe contener código HTML.')


def validate_code_safety(code: str) -> list:
    """
    Validate Python code for dangerous patterns WITHOUT blocking functionality.
    Returns a list of warning messages (empty if safe).
    Does NOT block the code — only flags dangerous patterns.
    """
    warnings = []
    if not code:
        return warnings

    if len(code) > MAX_CODE_LENGTH:
        warnings.append(f'El código excede el límite de {MAX_CODE_LENGTH} caracteres.')
        return warnings

    # Check for import statements of dangerous modules
    import_pattern = re.compile(
        r'(?:^|;|\s)(?:import|from)\s+(' + '|'.join(re.escape(m) for m in DANGEROUS_MODULES) + r')\b',
        re.MULTILINE
    )
    matches = import_pattern.findall(code)
    if matches:
        warnings.append(f'El código contiene imports no permitidos: {", ".join(set(matches))}')

    # Check for dangerous function calls / attribute access
    for kw in DANGEROUS_KEYWORDS:
        if kw in code:
            warnings.append(f'El código contiene el patrón no permitido: {kw}')
            break

    # Check for open() calls
    if re.search(r'\bopen\s*\(', code):
        warnings.append('El código contiene llamadas a open() que no están permitidas.')

    return warnings

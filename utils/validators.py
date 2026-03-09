"""
Utility validators for the SEA-API project
"""

import re
from typing import Any, Dict


def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email string to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength
    
    Args:
        password: Password string to validate
        
    Returns:
        dict: Validation result with 'valid' and 'message' keys
    """
    if len(password) < 8:
        return {
            'valid': False,
            'message': 'La contraseña debe tener al menos 8 caracteres'
        }
    
    if not re.search(r'[A-Z]', password):
        return {
            'valid': False,
            'message': 'La contraseña debe contener al menos una letra mayúscula'
        }
    
    if not re.search(r'[a-z]', password):
        return {
            'valid': False,
            'message': 'La contraseña debe contener al menos una letra minúscula'
        }
    
    if not re.search(r'\d', password):
        return {
            'valid': False,
            'message': 'La contraseña debe contener al menos un número'
        }
    
    return {
        'valid': True,
        'message': 'Contraseña válida'
    }

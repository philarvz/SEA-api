"""
Utility functions and helpers for the SEA-API project
"""

from typing import Dict, Any
from rest_framework.response import Response
from rest_framework import status


def success_response(data: Any, message: str = None, status_code: int = status.HTTP_200_OK) -> Response:
    """
    Standard success response format
    
    Args:
        data: Response data
        message: Success message (optional)
        status_code: HTTP status code
        
    Returns:
        Response: Formatted response
    """
    response_data = {
        'success': True,
        'data': data
    }
    
    if message:
        response_data['message'] = message
    
    return Response(response_data, status=status_code)


def error_response(message: str, errors: Dict = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    """
    Standard error response format
    
    Args:
        message: Error message
        errors: Detailed errors (optional)
        status_code: HTTP status code
        
    Returns:
        Response: Formatted response
    """
    response_data = {
        'success': False,
        'message': message
    }
    
    if errors:
        response_data['errors'] = errors
    
    return Response(response_data, status=status_code)

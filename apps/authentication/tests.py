"""
Authentication Tests
"""

from django.test import TestCase
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status

# Create your tests here.

class AuthenticationMockTestCase(APITestCase):
    """
    Test authentication with mock credentials
    """
    
    def test_login_with_valid_mock_credentials(self):
        """Test login with valid mock credentials"""
        url = '/api/v1/auth/login/'
        data = {
            'email': settings.MOCK_EMAIL,
            'password': settings.MOCK_PASSWORD
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
    
    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = '/api/v1/auth/login/'
        data = {
            'email': 'invalid@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_health_check(self):
        """Test health check endpoint"""
        url = '/api/v1/auth/health/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

"""
Utilidad para cifrado y descifrado de datos sensibles usando AES (compatible con CryptoJS).
"""

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from django.conf import settings
import base64
import hashlib
import json
from typing import Any, Dict


class CryptoService:
    """Servicio para cifrar y descifrar datos usando AES (compatible con CryptoJS)."""
    
    def __init__(self):
        # Usar clave desde settings (debe estar en .env)
        secret_key = getattr(settings, 'ENCRYPTION_KEY')
        
        if not secret_key:
            raise ValueError('ENCRYPTION_KEY no está configurada en las variables de entorno')
        
        if isinstance(secret_key, bytes):
            secret_key = secret_key.decode()
        
        self.secret_key = secret_key
    
    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """
        Cifra un diccionario de datos y retorna una cadena base64 (compatible con CryptoJS).
        
        Args:
            data: Diccionario con los datos a cifrar
            
        Returns:
            String cifrado en base64
        """
        json_data = json.dumps(data)
        
        # Generar salt aleatorio de 8 bytes
        salt = get_random_bytes(8)
        
        # Derivar clave e IV usando EVP_BytesToKey (compatible con CryptoJS)
        key_iv = self._derive_key_and_iv(self.secret_key, salt)
        key = key_iv[:32]  # Primeros 32 bytes para AES-256
        iv = key_iv[32:48]  # Siguientes 16 bytes para IV
        
        # Cifrar usando AES-256-CBC
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(json_data.encode('utf-8'), AES.block_size)
        ciphertext = cipher.encrypt(padded_data)
        
        # Formato compatible con CryptoJS: "Salted__" + salt + ciphertext
        result = b'Salted__' + salt + ciphertext
        
        return base64.b64encode(result).decode('utf-8')
    
    def decrypt_data(self, encrypted_string: str) -> Dict[str, Any]:
        """
        Descifra una cadena base64 (de CryptoJS) y retorna el diccionario original.
        
        Args:
            encrypted_string: String cifrado en base64
            
        Returns:
            Diccionario con los datos descifrados
            
        Raises:
            ValueError: Si el dato está corrupto o la clave es incorrecta
        """
        try:
            # Decodificar base64
            encrypted_bytes = base64.b64decode(encrypted_string)
            
            # Verificar formato CryptoJS
            if encrypted_bytes[:8] != b'Salted__':
                raise ValueError('Formato inválido')
            
            # Extraer salt y ciphertext
            salt = encrypted_bytes[8:16]
            ciphertext = encrypted_bytes[16:]
            
            # Derivar clave e IV usando EVP_BytesToKey (compatible con CryptoJS)
            key_iv = self._derive_key_and_iv(self.secret_key, salt)
            key = key_iv[:32]
            iv = key_iv[32:48]
            
            # Descifrar
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(ciphertext)
            
            # Remover padding
            unpadded = unpad(decrypted, AES.block_size)
            
            # Decodificar JSON
            return json.loads(unpadded.decode('utf-8'))
        except Exception as e:
            raise ValueError(f'Error al descifrar datos: {str(e)}')
    
    def _derive_key_and_iv(self, password: str, salt: bytes, key_length: int = 32, iv_length: int = 16) -> bytes:
        """
        Deriva clave e IV usando EVP_BytesToKey (compatible con CryptoJS).
        Implementación equivalente a OpenSSL EVP_BytesToKey con MD5.
        """
        d = d_i = b''
        password_bytes = password.encode('utf-8')
        
        while len(d) < key_length + iv_length:
            d_i = hashlib.md5(d_i + password_bytes + salt).digest()
            d += d_i
        
        return d[:key_length + iv_length]


# Instancia singleton
crypto_service = CryptoService()

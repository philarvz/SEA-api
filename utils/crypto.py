"""
Utilidad para cifrado y descifrado de datos sensibles usando AES-GCM (modo seguro).
Soporta compatibilidad con formato legacy CryptoJS (AES-CBC) para migración gradual.
"""

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from django.conf import settings
import base64
import hashlib
import json
from typing import Any, Dict


class CryptoService:
    """Servicio para cifrar y descifrar datos usando AES-GCM (modo seguro)."""
    
    def __init__(self):
        # Usar clave desde settings (debe estar en .env)
        secret_key = getattr(settings, 'ENCRYPTION_KEY')
        
        if not secret_key:
            raise ValueError('ENCRYPTION_KEY no está configurada en las variables de entorno')
        
        # Guardar clave como string para CBC legacy
        if isinstance(secret_key, bytes):
            self.secret_key_str = secret_key.decode('utf-8')
            self.secret_key_bytes = secret_key
        else:
            self.secret_key_str = secret_key
            # Convertir string a bytes de 32 bytes para AES-256-GCM
            self.secret_key_bytes = secret_key.encode('utf-8')[:32].ljust(32, b'\0')
    
    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """
        Cifra un diccionario de datos y retorna una cadena base64 usando AES-GCM.
        
        Args:
            data: Diccionario con los datos a cifrar
            
        Returns:
            String cifrado en base64
        """
        json_data = json.dumps(data)
        
        # Generar nonce aleatorio (96 bits recomendado para GCM)
        nonce = get_random_bytes(12)
        
        # Cifrar usando AES-256-GCM (modo seguro)
        cipher = AES.new(self.secret_key_bytes, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(json_data.encode('utf-8'))
        
        # Formato: nonce + tag + ciphertext
        result = nonce + tag + ciphertext
        
        return base64.b64encode(result).decode('utf-8')
    
    def decrypt_data(self, encrypted_string: str) -> Dict[str, Any]:
        """
        Descifra una cadena base64 y retorna el diccionario original.
        Soporta formato GCM (nuevo) y CBC legacy (CryptoJS) para compatibilidad.
        
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
            
            # Verificar si es formato CryptoJS legacy (comienza con "Salted__")
            if encrypted_bytes[:8] == b'Salted__':
                return self._decrypt_legacy_cbc(encrypted_bytes)
            else:
                return self._decrypt_gcm(encrypted_bytes)
                
        except Exception as exc:
            raise ValueError(f'Error al descifrar datos: {str(exc)}')
    
    def _decrypt_gcm(self, encrypted_bytes: bytes) -> Dict[str, Any]:
        """Descifra datos usando AES-GCM (formato Web Crypto API)"""
        # Extraer nonce (primeros 12 bytes)
        nonce = encrypted_bytes[:12]
        
        # El resto es ciphertext + tag (tag incluido al final por Web Crypto API)
        ciphertext_with_tag = encrypted_bytes[12:]
        
        # Separar tag (últimos 16 bytes) del ciphertext
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]
        
        # Descifrar usando AES-GCM
        cipher = AES.new(self.secret_key_bytes, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        
        # Decodificar JSON
        return json.loads(decrypted.decode('utf-8'))
    
    def _decrypt_legacy_cbc(self, encrypted_bytes: bytes) -> Dict[str, Any]:
        """Descifra datos usando AES-CBC (formato CryptoJS legacy para compatibilidad)"""
        # Extraer salt y ciphertext del formato CryptoJS
        salt = encrypted_bytes[8:16]
        ciphertext = encrypted_bytes[16:]
        
        # Derivar clave e IV usando EVP_BytesToKey (compatible con CryptoJS)
        key_iv = self._derive_key_and_iv(self.secret_key_str, salt)
        key = key_iv[:32]
        iv = key_iv[32:48]
        
        # Descifrar usando AES-CBC (legacy support only - nuevo código debe usar GCM)
        cipher = AES.new(key, AES.MODE_CBC, iv)  # NOSONAR - Legacy compatibility
        decrypted = cipher.decrypt(ciphertext)
        
        # Remover padding
        unpadded = unpad(decrypted, AES.block_size)
        
        # Decodificar JSON
        return json.loads(unpadded.decode('utf-8'))
    
    def _derive_key_and_iv(self, secret: str, salt: bytes, key_length: int = 32, iv_length: int = 16) -> bytes:
        """
        Deriva clave e IV usando EVP_BytesToKey (compatible con CryptoJS).
        Solo para compatibilidad con datos legacy. MD5 se usa aquí únicamente
        para mantener compatibilidad con el formato CryptoJS existente.
        IMPORTANTE: Nuevo código debe usar AES-GCM que no requiere este método.
        """
        d = d_i = b''
        secret_bytes = secret.encode('utf-8')
        
        while len(d) < key_length + iv_length:
            d_i = hashlib.md5(d_i + secret_bytes + salt).digest()  # NOSONAR - Legacy compatibility only
            d += d_i
        
        return d[:key_length + iv_length]


# Instancia singleton
crypto_service = CryptoService()

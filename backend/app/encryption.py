"""Encryption/Decryption utility for API secrets"""
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class Encryption:
    """Handle encryption and decryption of API credentials"""
    
    def __init__(self, secret_key: str):
        """
        Initialize encryption with secret key
        
        Args:
            secret_key: The secret key used for encryption/decryption
        """
        self.secret_key = secret_key
        self.algorithm = 'aes-256-cbc'
    
    def generate_sha256(self, text: str) -> str:
        """Generate SHA256 hash of text"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt text using AES-256-CBC
        
        Args:
            encrypted_text: Encrypted text in format 'iv:encrypted_data' (hex)
        
        Returns:
            Decrypted plaintext string
        """
        try:
            # Split IV and encrypted data
            text_parts = encrypted_text.split(':')
            iv = bytes.fromhex(text_parts[0])
            encrypted_data = bytes.fromhex(':'.join(text_parts[1:]))
            
            # Create key from secret using SHA256
            key = hashlib.sha256(self.secret_key.encode()).digest()
            
            # Create cipher and decrypt
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            
            return decrypted.decode('utf-8')
        except Exception as e:
            raise Exception(f'Decryption failed: {str(e)}')
    
    def decrypt_api_secret(self, encrypted_api_secret: str) -> str:
        """Decrypt API secret for use"""
        return self.decrypt(encrypted_api_secret)
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage (one-way hash)"""
        return self.generate_sha256(api_key)


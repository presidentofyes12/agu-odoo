from odoo import models, api
from cryptography.fernet import Fernet
import base64
import logging

_logger = logging.getLogger(__name__)

class WalletUtils(models.AbstractModel):
    _name = 'wallet.utils'
    _description = 'Wallet Utilities'

    @api.model
    def _get_encryption_key(self):
        """Get or create encryption key from system parameters"""
        param = self.env['ir.config_parameter'].sudo()
        key = param.get_param('web3_wallet.encryption_key')
        if not key:
            key = Fernet.generate_key()
            param.set_param('web3_wallet.encryption_key', key.decode())
        return key if isinstance(key, bytes) else key.encode()

    @api.model
    def encrypt_private_key(self, private_key):
        """Encrypt private key using Fernet symmetric encryption"""
        try:
            if not private_key:
                return None
                
            f = Fernet(self._get_encryption_key())
            encrypted = f.encrypt(private_key.encode())
            return base64.b64encode(encrypted).decode()
            
        except Exception as e:
            _logger.error(f"Encryption failed: {str(e)}")
            raise ValueError("Failed to encrypt private key")

    @api.model
    def decrypt_private_key(self, encrypted_key):
        """Decrypt private key using Fernet symmetric encryption"""
        try:
            if not encrypted_key:
                return None
                
            f = Fernet(self._get_encryption_key())
            encrypted = base64.b64decode(encrypted_key.encode())
            decrypted = f.decrypt(encrypted)
            return decrypted.decode()
            
        except Exception as e:
            _logger.error(f"Decryption failed: {str(e)}")
            raise ValueError("Failed to decrypt private key")

    @api.model
    def validate_address(self, address):
        """Validate Ethereum address format"""
        if not address:
            return False
        if not address.startswith('0x'):
            address = '0x' + address
        return self.env['wallet.config'].get_web3_connection().is_address(address)

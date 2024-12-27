from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from web3.auto import w3
import logging
from cryptography.fernet import Fernet
import base64

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Web3 Fields
    eth_address = fields.Char('ETH Address', copy=False)
    eth_private_key = fields.Char('Private Key', copy=False, groups="web3_wallet_connect.group_wallet_admin")
    current_chain_id = fields.Integer('Current Chain ID')
    
    # Nostr Fields
    nostr_public_key = fields.Char('Nostr Public Key', copy=False)
    nostr_private_key = fields.Char('Nostr Private Key', copy=False, groups="web3_wallet_connect.group_wallet_admin")
    
    # Common Fields
    is_wallet_connected = fields.Boolean('Wallet Connected', default=False)
    last_connection_type = fields.Selection([
        ('web3', 'Web3'),
        ('nostr', 'Nostr')
    ], string='Last Connection Type')
    wallet_connection_ids = fields.One2many('wallet.connection', 'user_id', string='Wallet Connections')

    _sql_constraints = [
        ('eth_address_unique', 'UNIQUE(eth_address)',
         'This Ethereum address is already registered!')
    ]

    @api.model
    def _get_encryption_key(self):
        """Get or create encryption key from system parameters"""
        param = self.env['ir.config_parameter'].sudo()
        key = param.get_param('web3_wallet_connect.encryption_key')
        if not key:
            key = Fernet.generate_key()
            param.set_param('web3_wallet_connect.encryption_key', key.decode())
        return key if isinstance(key, bytes) else key.encode()

    def _encrypt_key(self, key):
        """Encrypt private key"""
        if not key:
            return False
        try:
            f = Fernet(self._get_encryption_key())
            return base64.b64encode(f.encrypt(key.encode())).decode()
        except Exception as e:
            raise UserError(f"Encryption failed: {str(e)}")

    def _decrypt_key(self, encrypted_key):
        """Decrypt private key"""
        if not encrypted_key:
            return False
        try:
            f = Fernet(self._get_encryption_key())
            encrypted = base64.b64decode(encrypted_key.encode())
            return f.decrypt(encrypted).decode()
        except Exception as e:
            raise UserError(f"Decryption failed: {str(e)}")

    @api.constrains('eth_address')
    def _check_eth_address(self):
        """Validate Ethereum address format"""
        for record in self:
            if record.eth_address and not w3.is_address(record.eth_address):
                raise ValidationError("Invalid Ethereum address format")

    def create_web3_wallet(self):
        """Create new Web3 wallet"""
        account = w3.eth.account.create()
        self.write({
            'eth_address': account.address,
            'eth_private_key': self._encrypt_key(account.key.hex()),
            'is_wallet_connected': True,
            'last_connection_type': 'web3'
        })
        return {'address': account.address}

    def create_nostr_wallet(self):
        """Create new Nostr wallet"""
        # Implement Nostr key generation
        pass

    @api.model
    def _update_wallet_balances(self):
        """Cron job to update wallet balances"""
        users = self.search([('is_wallet_connected', '=', True)])
        for user in users:
            for connection in user.wallet_connection_ids:
                connection.update_balance()

    def disconnect_wallet(self):
        """Disconnect active wallet"""
        self.write({
            'is_wallet_connected': False,
            'last_connection_type': False
        })
        for connection in self.wallet_connection_ids:
            connection.disconnect()

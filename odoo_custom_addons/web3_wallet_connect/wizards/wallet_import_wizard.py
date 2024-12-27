from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from eth_account import Account
import json
import logging

_logger = logging.getLogger(__name__)

class WalletImportWizard(models.TransientModel):
    _name = 'wallet.import.wizard'
    _description = 'Wallet Import Wizard'

    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    import_type = fields.Selection([
        ('private_key', 'Private Key'),
        ('json_file', 'Keystore JSON'),
        ('nostr_key', 'Nostr Key')
    ], required=True, default='private_key')
    
    private_key = fields.Char('Private Key')
    keystore_file = fields.Binary('Keystore File')
    keystore_password = fields.Char('Keystore Password')
    nostr_private_key = fields.Char('Nostr Private Key')
    
    @api.onchange('import_type')
    def _onchange_import_type(self):
        """Clear sensitive fields when changing import type"""
        self.private_key = False
        self.keystore_file = False
        self.keystore_password = False
        self.nostr_private_key = False

    def _validate_eth_private_key(self, private_key):
        """Validate Ethereum private key"""
        try:
            if private_key.startswith('0x'):
                private_key = private_key[2:]
            account = Account.from_key(private_key)
            return account
        except Exception as e:
            raise ValidationError(f"Invalid private key: {str(e)}")

    def _validate_keystore(self, keystore_file, password):
        """Validate keystore file and password"""
        try:
            keystore_json = json.loads(keystore_file.decode())
            private_key = Account.decrypt(keystore_json, password)
            account = Account.from_key(private_key)
            return account
        except Exception as e:
            raise ValidationError(f"Invalid keystore or password: {str(e)}")

    def _validate_nostr_key(self, private_key):
        """Validate Nostr private key"""
        # Add Nostr-specific validation logic here
        return True

    def action_import(self):
        """Import wallet based on selected method"""
        self.ensure_one()
        
        if not self.user_id:
            raise UserError("No user specified for wallet import")

        try:
            if self.import_type == 'private_key':
                if not self.private_key:
                    raise ValidationError("Private key is required")
                account = self._validate_eth_private_key(self.private_key)
                self.user_id.write({
                    'eth_address': account.address,
                    'eth_private_key': self.private_key,
                    'is_wallet_connected': True
                })
                
            elif self.import_type == 'json_file':
                if not self.keystore_file or not self.keystore_password:
                    raise ValidationError("Keystore file and password are required")
                account = self._validate_keystore(self.keystore_file, self.keystore_password)
                self.user_id.write({
                    'eth_address': account.address,
                    'eth_private_key': account.key.hex(),
                    'is_wallet_connected': True
                })
                
            elif self.import_type == 'nostr_key':
                if not self.nostr_private_key:
                    raise ValidationError("Nostr private key is required")
                self._validate_nostr_key(self.nostr_private_key)
                self.user_id.write({
                    'nostr_private_key': self.nostr_private_key,
                    'is_wallet_connected': True
                })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Wallet imported successfully',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f"Failed to import wallet: {str(e)}")

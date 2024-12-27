from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from eth_account import Account
import secrets
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    eth_address = fields.Char('Ethereum Address', readonly=True, copy=False, 
                             tracking=True)
    encrypted_key = fields.Text('Encrypted Private Key', 
                              copy=False, readonly=True,
                              groups="web3_wallet.group_wallet_manager")
    active_network_id = fields.Many2one('wallet.config', string='Active Network',
                                      domain=[('active', '=', True)])
    wallet_balance = fields.Float('Wallet Balance', digits=(18, 8), 
                                compute='_compute_wallet_balance',
                                tracking=True)
    wallet_state = fields.Selection([
        ('none', 'No Wallet'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Wallet Status', compute='_compute_wallet_state',
       store=True, default='none')
    transaction_count = fields.Integer('Transaction Count', 
                                     compute='_compute_transaction_count')
    last_activity = fields.Datetime('Last Activity')

    _sql_constraints = [
        ('eth_address_unique', 
         'UNIQUE(eth_address)',
         'This Ethereum address is already registered!')
    ]

    @api.depends('eth_address')
    def _compute_wallet_state(self):
        for user in self:
            if user.eth_address:
                user.wallet_state = 'active'
            else:
                user.wallet_state = 'none'

    @api.model
    def get_wallet_dashboard_data(self):
        """Get data for wallet dashboard"""
        user = self.env.user
        data = {
            'has_wallet': bool(user.eth_address),
            'address': user.eth_address or False,
            'balance': user.wallet_balance,
            'currency': user.active_network_id.network_currency if user.active_network_id else 'ETH',
            'transaction_count': user.transaction_count,
            'pending_count': self.env['wallet.transaction'].search_count([
                ('user_id', '=', user.id),
                ('state', '=', 'pending')
            ]),
            'network_name': user.active_network_id.name if user.active_network_id else 'Not Connected',
            'gas_price': False,
        }
        
        if user.active_network_id:
            try:
                web3 = user.active_network_id.get_web3_connection()
                data['gas_price'] = float(web3.from_wei(web3.eth.gas_price, 'gwei'))
            except Exception as e:
                _logger.error(f"Failed to get gas price: {str(e)}")
        
        return data
    
    @api.depends('eth_address', 'active_network_id')
    def _compute_wallet_balance(self):
        for user in self:
            balance = 0.0
            if user.eth_address and user.active_network_id:
                try:
                    web3 = user.active_network_id.get_web3_connection()
                    balance_wei = web3.eth.get_balance(user.eth_address)
                    balance = float(web3.from_wei(balance_wei, 'ether'))
                except Exception as e:
                    _logger.error(f"Failed to get balance: {str(e)}")
            user.wallet_balance = balance

    @api.depends('eth_address')
    def _compute_transaction_count(self):
        for user in self:
            count = 0
            if user.eth_address:
                count = self.env['wallet.transaction'].search_count([
                    '|',
                    ('from_address', '=', user.eth_address),
                    ('to_address', '=', user.eth_address)
                ])
            user.transaction_count = count

    def create_web3_wallet(self):
        """Create new Ethereum wallet"""
        self.ensure_one()
        if self.eth_address:
            raise UserError("User already has a wallet associated")

        try:
            # Generate new account
            account = Account.create(extra_entropy=secrets.token_bytes(32))
            private_key = account.key.hex()
            
            # Encrypt private key before storage
            encrypted_key = self.env['wallet.utils'].encrypt_private_key(private_key)
            
            # Update user record
            self.write({
                'eth_address': account.address,
                'encrypted_private_key': encrypted_key,
                'last_activity': fields.Datetime.now()
            })

            # Create default connection
            default_network = self.env['wallet.config'].search(
                [('active', '=', True)], limit=1)
            if default_network:
                self.env['wallet.connection'].create({
                    'user_id': self.id,
                    'network_id': default_network.id,
                    'address': account.address,
                    'status': 'connected'
                })

            return {
                'address': account.address,
                'private_key': private_key,  # Return only for initial setup
            }

        except Exception as e:
            _logger.error(f"Wallet creation failed: {str(e)}")
            raise UserError(f"Failed to create wallet: {str(e)}")

    def import_wallet(self, private_key):
        """Import existing wallet using private key"""
        self.ensure_one()
        if self.eth_address:
            raise UserError("User already has a wallet associated")

        try:
            # Validate and derive address from private key
            if private_key.startswith('0x'):
                private_key = private_key[2:]
            account = Account.from_key(private_key)
            
            # Encrypt private key
            encrypted_key = self.env['wallet.utils'].encrypt_private_key(private_key)
            
            # Update user record
            self.write({
                'eth_address': account.address,
                'encrypted_private_key': encrypted_key,
                'last_activity': fields.Datetime.now()
            })

            return {'address': account.address}

        except Exception as e:
            _logger.error(f"Wallet import failed: {str(e)}")
            raise UserError(f"Failed to import wallet: {str(e)}")

    def _get_wallet_private_key(self):
        """Get decrypted private key for transaction signing"""
        self.ensure_one()
        if not self.encrypted_key:
            return None
            
        try:
            return self.env['wallet.utils'].decrypt_private_key(self.encrypted_key)
        except Exception as e:
            _logger.error(f"Failed to decrypt key: {str(e)}")
            return None

    def action_create_wallet(self):
        """Create new wallet"""
        self.ensure_one()
        if self.eth_address:
            raise UserError("User already has a wallet")

        try:
            account = Account.create(extra_entropy=secrets.token_bytes(32))
            private_key = account.key.hex()
            
            # Encrypt private key
            encrypted_key = self.env['wallet.utils'].encrypt_private_key(private_key)
            
            # Update record
            self.write({
                'eth_address': account.address,
                'encrypted_key': encrypted_key,
                'last_activity': fields.Datetime.now()
            })
            
            # Return address only in notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Wallet created with address: {account.address}',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Wallet creation failed: {str(e)}")
            raise UserError(f"Failed to create wallet: {str(e)}")

    def action_import_wallet(self):
        """Open import wallet wizard"""
        self.ensure_one()
        return {
            'name': 'Import Wallet',
            'type': 'ir.actions.act_window',
            'res_model': 'wallet.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.id}
        }

    def sign_message(self, message):
        """Sign a message with the wallet's private key"""
        self.ensure_one()
        if not self.eth_address:
            raise UserError("No wallet associated with this user")

        try:
            private_key = self._get_wallet_private_key()
            if not private_key:
                raise UserError("Private key not available")

            account = Account.from_key(private_key)
            signed_message = account.sign_message(message)
            
            return {
                'message': message,
                'signature': signed_message.signature.hex(),
                'address': account.address
            }

        except Exception as e:
            _logger.error(f"Message signing failed: {str(e)}")
            raise UserError(f"Failed to sign message: {str(e)}")

    @api.model
    def rotate_encryption_keys(self):
        """Rotate encryption keys for all stored private keys"""
        users = self.search([('encrypted_private_key', '!=', False)])
        utils = self.env['wallet.utils']
        
        for user in users:
            try:
                # Decrypt with old key
                private_key = utils.decrypt_private_key(user.encrypted_private_key)
                # Re-encrypt with new key
                new_encrypted_key = utils.encrypt_private_key(private_key)
                user.encrypted_private_key = new_encrypted_key
            except Exception as e:
                _logger.error(f"Key rotation failed for user {user.id}: {str(e)}")

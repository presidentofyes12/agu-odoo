# models/dao_member.py
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from eth_account import Account
from eth_keys import keys
import json
import logging
from cryptography.fernet import Fernet
import base64

_logger = logging.getLogger(__name__)

class DAOMember(models.Model):
    _inherit = 'res.users'

    # once transactions work regulate private key viewing to prevent anyone from being able to see other members private keys

    eth_address = fields.Char('Ethereum Address')
    #eth_private_key = fields.Char('Private Key') # , groups='dao_core.group_dao_admin'
    eth_private_key = fields.Char(
        'Private Key', 
        groups=False,  # Make field visible to all users
        copy=False,    # Security measure: don't copy during duplicate
        tracking=True  # Track changes to the field
    )
    member_type = fields.Selection([
        ('regular', 'Regular Member'),
        ('admin', 'Admin'),
        ('auditor', 'Auditor')
    ], default='regular')
    dao_ids = fields.Many2many('dao.config', string='Associated DAOs')
    active_dao_id = fields.Many2one('dao.config', string='Active DAO')
    encrypted_private_key = fields.Binary('Encrypted Private Key', groups='dao_core.group_dao_admin')
    
    # New fields
    wallet_balance = fields.Float('Wallet Balance', compute='_compute_wallet_balance')
    transaction_count = fields.Integer('Transaction Count', compute='_compute_transaction_count')
    last_activity = fields.Datetime('Last Activity')
    is_wallet_connected = fields.Boolean('Wallet Connected', default=False)

    @api.constrains('eth_address')
    def _check_eth_address(self):
        for record in self:
            if record.eth_address and not self.env['dao.config'].get_web3_connection().is_address(record.eth_address):
                raise ValidationError("Invalid Ethereum address format")

    def create_wallet(self):
        """Create new Ethereum wallet with enhanced security"""
        try:
            web3_manager = self.env['dao.config'].get_web3_manager()
            wallet_data = web3_manager.create_wallet()
            
            self.write({
                'eth_address': wallet_data['address'],
                'encrypted_private_key': wallet_data['encrypted_key'],
                'is_wallet_connected': True,
                'last_activity': fields.Datetime.now()
            })
            
            # Create initial DAO membership
            if self.env.context.get('default_dao_id'):
                self.dao_ids = [(4, self.env.context['default_dao_id'])]
                self.active_dao_id = self.env.context['default_dao_id']
            
            return {'address': wallet_data['address']}
            
        except Exception as e:
            _logger.error(f"Wallet creation failed: {str(e)}")
            raise UserError(f"Failed to create wallet: {str(e)}")

    @api.depends('eth_address')
    def _compute_wallet_balance(self):
        """Compute current wallet balance"""
        web3 = self.env['dao.config'].get_web3_connection()
        for record in self:
            if record.eth_address:
                try:
                    record.wallet_balance = web3.eth.get_balance(record.eth_address)
                except Exception as e:
                    _logger.error(f"Balance check failed: {str(e)}")
                    record.wallet_balance = 0
            else:
                record.wallet_balance = 0

    @api.depends('eth_address')
    def _compute_transaction_count(self):
        """Compute number of transactions"""
        for record in self:
            record.transaction_count = self.env['dao.transaction'].search_count([
                '|',
                ('from_address', '=', record.eth_address),
                ('to_address', '=', record.eth_address)
            ])

    def sign_transaction(self, transaction_data):
        """Sign transaction with member's private key"""
        try:
            if not self.encrypted_private_key:
                raise UserError("No private key available")
                
            web3_manager = self.env['dao.config'].get_web3_manager()
            private_key = web3_manager._decrypt_private_key(self.encrypted_private_key)
            
            signed_tx = web3_manager.sign_transaction(transaction_data, private_key)
            return signed_tx
            
        except Exception as e:
            _logger.error(f"Transaction signing failed: {str(e)}")
            raise UserError(f"Failed to sign transaction: {str(e)}")

    def send_transaction(self, to_address, value, data=None):
        """Send transaction from member's wallet"""
        try:
            if not self.eth_address:
                raise UserError("No wallet address available")
                
            web3_manager = self.env['dao.config'].get_web3_manager()
            tx_params = web3_manager.create_transaction(
                self.eth_address,
                to_address,
                value,
                data
            )
            
            signed_tx = self.sign_transaction(tx_params)
            tx_hash = web3_manager.send_transaction(signed_tx)
            
            # Create transaction record
            self.env['dao.transaction'].create({
                'name': f"Transaction from {self.name}",
                'transaction_hash': tx_hash,
                'from_address': self.eth_address,
                'to_address': to_address,
                'value': value,
                'status': 'pending'
            })
            
            self.last_activity = fields.Datetime.now()
            return tx_hash
            
        except Exception as e:
            _logger.error(f"Transaction sending failed: {str(e)}")
            raise UserError(f"Failed to send transaction: {str(e)}")

    def connect_external_wallet(self, address):
        """Connect existing external wallet"""
        try:
            web3 = self.env['dao.config'].get_web3_connection()
            if not web3.is_address(address):
                raise ValidationError("Invalid Ethereum address")
                
            self.write({
                'eth_address': address,
                'is_wallet_connected': True,
                'last_activity': fields.Datetime.now()
            })
            
        except Exception as e:
            _logger.error(f"External wallet connection failed: {str(e)}")
            raise UserError(f"Failed to connect wallet: {str(e)}")
        
    @api.model
    def _get_encryption_key(self):
        """Get or create encryption key from system parameters"""
        param = self.env['ir.config_parameter'].sudo()
        key = param.get_param('dao.encryption_key')
        if not key:
            key = Fernet.generate_key()
            param.set_param('dao.encryption_key', key.decode())
        return key if isinstance(key, bytes) else key.encode()

    def clear_private_key(self):
        """Clear private key from memory after use"""
        self.eth_private_key = False
        
    @api.model
    def rotate_encryption_key(self):
        """Rotate encryption key and re-encrypt existing keys"""
        # Implementation for key rotation
        pass

    @api.model
    def _encrypt_private_key(self, private_key):
        if not private_key:
            return False
        try:
            # Validate private key format
            if len(private_key.replace('0x', '')) != 64:
                raise ValidationError("Invalid private key format")
                
            f = Fernet(self._get_encryption_key())
            return base64.b64encode(f.encrypt(private_key.encode())).decode()
        except Exception as e:
            _logger.error(f"Private key encryption failed: {str(e)}")
            raise UserError("Failed to secure private key")

    def _decrypt_private_key(self):
        """Decrypt stored private key"""
        if not self.eth_private_key:
            return False
        try:
            f = Fernet(self._get_encryption_key())
            encrypted = base64.b64decode(self.eth_private_key.encode())
            return f.decrypt(encrypted).decode()
        except Exception as e:
            _logger.error(f"Failed to decrypt private key: {str(e)}")
            raise UserError("Could not decrypt private key")

    @api.model
    def create(self, vals):
        if vals.get('eth_private_key'):
            vals['eth_private_key'] = self._encrypt_private_key(vals['eth_private_key'])
        return super(DAOMember, self).create(vals)

    def write(self, vals):
        if vals.get('eth_private_key'):
            vals['eth_private_key'] = self._encrypt_private_key(vals['eth_private_key'])
        return super(DAOMember, self).write(vals)

    def test_wallet_connection(self):
        """Test wallet connection and balance"""
        self.ensure_one()
        try:
            web3 = self.env['dao.config'].get_web3_connection()
            balance = web3.eth.get_balance(self.eth_address)
            balance_eth = web3.from_wei(balance, 'ether')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Wallet Test Successful',
                    'message': f'Connected successfully. Balance: {balance_eth} ETH',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f"Wallet connection failed: {str(e)}")

    @api.constrains('eth_private_key')
    def _check_private_key(self):
        """Validate private key format and derivation of address"""
        for record in self:
            if record.eth_private_key and record.eth_address:
                try:
                    decrypted_key = record._decrypt_private_key()
                    if decrypted_key:
                        # Remove '0x' prefix if present
                        clean_key = decrypted_key.replace('0x', '')
                        account = Account.from_key(clean_key)
                        if account.address.lower() != record.eth_address.lower():
                            raise ValidationError("Private key does not match the Ethereum address")
                except Exception as e:
                    raise ValidationError(f"Invalid private key format: {str(e)}")

    @api.onchange('eth_private_key')
    def _onchange_private_key(self):
        """Update address when private key is changed"""
        if self.eth_private_key:
            try:
                # Remove '0x' prefix if present
                clean_key = self.eth_private_key.replace('0x', '')
                account = Account.from_key(clean_key)
                self.eth_address = account.address
                self.is_wallet_connected = True
            except Exception as e:
                raise UserError(f"Invalid private key: {str(e)}")

    def import_existing_wallet(self):
        """Import an existing wallet using private key"""
        return {
            'name': 'Import Existing Wallet',
            'type': 'ir.actions.act_window',
            'res_model': 'dao.wallet.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.id}
        }
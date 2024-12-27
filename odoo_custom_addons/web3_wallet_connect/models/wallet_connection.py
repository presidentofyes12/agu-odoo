from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class WalletConnection(models.Model):
    _name = 'wallet.connection'
    _description = 'Wallet Connection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    connection_type = fields.Selection([
        ('web3', 'Web3 Wallet'),
        ('nostr', 'Nostr')
    ], required=True)
    
    # Web3 specific fields
    eth_address = fields.Char('ETH Address')
    chain_id = fields.Integer('Chain ID')
    balance = fields.Float('Balance', digits=(18, 8))
    last_block_check = fields.Integer('Last Block Check')
    
    # Nostr specific fields
    nostr_public_key = fields.Char('Nostr Public Key')
    connected_relays = fields.Text('Connected Relays')
    
    state = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error')
    ], default='disconnected', tracking=True)
    
    last_connection = fields.Datetime('Last Connection', tracking=True)
    last_error = fields.Text('Last Error')

    _sql_constraints = [
        ('user_type_unique', 'UNIQUE(user_id, connection_type)',
         'A user can only have one connection per type!')
    ]

    @api.depends('user_id', 'connection_type')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.user_id.name}'s {record.connection_type} connection"

    def action_connect(self):
        """Initiate wallet connection"""
        self.ensure_one()
        if self.connection_type == 'web3':
            return {
                'type': 'ir.actions.client',
                'tag': 'web3_wallet_connect.connect',  # Changed this tag
                'name': 'Connect Wallet',
                'target': 'new',
            }
        elif self.connection_type == 'nostr':
            return self._connect_nostr()

    def _connect_web3(self):
        """Handle Web3 wallet connection"""
        return {
            'type': 'ir.actions.client',
            'tag': 'wallet_connector',
            'params': {
                'connection_id': self.id,
                'connection_type': 'web3'
            }
        }

    def _connect_nostr(self):
        """Handle Nostr connection"""
        return {
            'type': 'ir.actions.client',
            'tag': 'wallet_connector',
            'params': {
                'connection_id': self.id,
                'connection_type': 'nostr'
            }
        }

    def _handle_connection_error(self, error_message):
        """Handle connection errors"""
        self.write({
            'state': 'error',
            'last_error': error_message
        })
        raise UserError(f"Connection failed: {error_message}")

    def update_balance(self):
        """Update wallet balance"""
        for record in self:
            if record.connection_type == 'web3' and record.eth_address:
                try:
                    web3 = self.env['wallet.config'].get_web3_connection()
                    balance_wei = web3.eth.get_balance(record.eth_address)
                    record.balance = web3.from_wei(balance_wei, 'ether')
                    record.last_block_check = web3.eth.block_number
                except Exception as e:
                    _logger.error(f"Failed to update balance: {str(e)}")

    def disconnect(self):
        """Disconnect wallet"""
        self.write({
            'state': 'disconnected',
            'last_error': False
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Wallet disconnected successfully',
                'type': 'success'
            }
        }

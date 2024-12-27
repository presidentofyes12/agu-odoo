from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class WalletConnection(models.Model):
    _name = 'wallet.connection'
    _description = 'Wallet Connection Status'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    network_id = fields.Many2one('wallet.config', required=True)
    address = fields.Char('Wallet Address', required=True)
    balance = fields.Float('Balance', digits=(18, 8), readonly=True)
    last_block_check = fields.Integer('Last Block Check', readonly=True)
    status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error')
    ], default='disconnected', required=True)
    last_connection = fields.Datetime('Last Connection')
    error_message = fields.Text('Error Message')

    _sql_constraints = [
        ('unique_user_network', 
         'UNIQUE(user_id, network_id)',
         'A user can only have one connection per network!')
    ]

    def update_balance(self):
        """Update wallet balance"""
        for conn in self:
            try:
                web3 = conn.network_id.get_web3_connection()
                balance_wei = web3.eth.get_balance(conn.address)
                conn.write({
                    'balance': web3.from_wei(balance_wei, 'ether'),
                    'last_block_check': web3.eth.block_number,
                    'status': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
            except Exception as e:
                conn.write({
                    'status': 'error',
                    'error_message': str(e)
                })
                _logger.error(f"Failed to update balance: {str(e)}")

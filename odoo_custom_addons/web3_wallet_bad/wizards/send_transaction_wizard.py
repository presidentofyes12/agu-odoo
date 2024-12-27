from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class SendTransactionWizard(models.TransientModel):
    _name = 'wallet.send.transaction.wizard'
    _description = 'Send Transaction Wizard'

    from_address = fields.Char('From', readonly=True)
    to_address = fields.Char('To', required=True)
    amount = fields.Float('Amount', required=True, digits=(18, 8))
    gas_price = fields.Float('Gas Price (Gwei)', digits=(18, 2))
    gas_limit = fields.Integer('Gas Limit', default=21000)
    network_id = fields.Many2one('wallet.config', string='Network', required=True,
                                domain=[('active', '=', True)])

    @api.model
    def default_get(self, fields):
        """Set default values"""
        res = super().default_get(fields)
        if self.env.user.eth_address:
            res['from_address'] = self.env.user.eth_address
            
        default_network = self.env['wallet.config'].search(
            [('active', '=', True)], limit=1)
        if default_network:
            res['network_id'] = default_network.id
            res['gas_price'] = float(default_network.get_gas_price())
            
        return res

    def action_send_transaction(self):
        """Create and send transaction"""
        self.ensure_one()
        
        try:
            transaction = self.env['wallet.transaction'].create({
                'name': f'Send {self.amount} ETH to {self.to_address}',
                'from_address': self.from_address,
                'to_address': self.to_address,
                'value': self.amount,
                'gas_price': self.gas_price,
                'gas_limit': self.gas_limit,
                'network_id': self.network_id.id,
            })
            
            transaction.action_send()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Transaction Sent',
                    'message': 'Transaction has been submitted to the network',
                    'type': 'success',
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'wallet.transaction',
                        'res_id': transaction.id,
                        'view_mode': 'form',
                    },
                }
            }
            
        except Exception as e:
            raise UserError(str(e))

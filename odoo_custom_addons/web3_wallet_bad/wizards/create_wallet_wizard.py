from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CreateWalletWizard(models.TransientModel):
    _name = 'wallet.create.wizard'
    _description = 'Create New Wallet Wizard'

    network_id = fields.Many2one('wallet.config', string='Network', required=True,
                                domain=[('active', '=', True)])
    show_private_key = fields.Boolean('Show Private Key', default=False)

    def action_create_wallet(self):
        """Create new wallet for current user"""
        self.ensure_one()
        user = self.env.user
        
        try:
            result = user.create_web3_wallet()
            if result.get('address'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Wallet created: {result["address"]}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            raise UserError(str(e))

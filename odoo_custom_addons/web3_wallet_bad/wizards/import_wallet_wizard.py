from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ImportWalletWizard(models.TransientModel):
    _name = 'wallet.import.wizard'
    _description = 'Import Existing Wallet'

    private_key = fields.Char('Private Key', required=True)
    network_id = fields.Many2one('wallet.config', string='Network', required=True,
                                domain=[('active', '=', True)])

    def action_import_wallet(self):
        """Import wallet using private key"""
        self.ensure_one()
        user = self.env.user
        
        try:
            result = user.import_wallet(self.private_key)
            if result.get('address'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Wallet imported: {result["address"]}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            raise UserError(str(e))

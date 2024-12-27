# models/res_config_settings.py
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_gas_limit = fields.Integer(
        string='Default Gas Limit',
        default=8000000,
        config_parameter='dao_core.default_gas_limit',
        default_model='dao.transaction'  # Add this line
    )

    transaction_confirmation_blocks = fields.Integer(
        string='Confirmation Blocks',
        default=12,
        config_parameter='dao_core.transaction_confirmation_blocks'
    )

    # Add other blockchain related settings
    gas_price_update_interval = fields.Integer(
        string='Gas Price Update Interval (minutes)',
        default=10,
        config_parameter='dao_core.gas_price_update_interval'
    )

    blockchain_sync_interval = fields.Integer(
        string='Blockchain Sync Interval (minutes)',
        default=15,
        config_parameter='dao_core.blockchain_sync_interval'
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        
        # Get values from system parameters
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            transaction_confirmation_blocks=int(params.get_param('dao_core.transaction_confirmation_blocks', 12)),
            gas_price_update_interval=int(params.get_param('dao_core.gas_price_update_interval', 10)),
            blockchain_sync_interval=int(params.get_param('dao_core.blockchain_sync_interval', 15))
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        
        # Store values in system parameters
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('dao_core.transaction_confirmation_blocks', self.transaction_confirmation_blocks)
        params.set_param('dao_core.gas_price_update_interval', self.gas_price_update_interval)
        params.set_param('dao_core.blockchain_sync_interval', self.blockchain_sync_interval)

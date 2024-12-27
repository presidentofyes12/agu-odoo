from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_gas_limit = fields.Integer(
        'Default Gas Limit',
        default=8000000,
        config_parameter='web3_wallet_connect.default_gas_limit'
    )

    balance_update_interval = fields.Integer(
        'Balance Update Interval (minutes)',
        default=5,
        config_parameter='web3_wallet_connect.balance_update_interval'
    )

    network_check_interval = fields.Integer(
        'Network Check Interval (minutes)',
        default=10,
        config_parameter='web3_wallet_connect.network_check_interval'
    )

    auto_disconnect_timeout = fields.Integer(
        'Auto Disconnect Timeout (minutes)',
        default=30,
        config_parameter='web3_wallet_connect.auto_disconnect_timeout'
    )

    default_gas_price_strategy = fields.Selection([
        ('legacy', 'Legacy'),
        ('eip1559', 'EIP-1559')
    ], default='legacy',
    config_parameter='web3_wallet_connect.default_gas_price_strategy')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        
        res.update(
            balance_update_interval=int(params.get_param('web3_wallet_connect.balance_update_interval', 5)),
            network_check_interval=int(params.get_param('web3_wallet_connect.network_check_interval', 10)),
            auto_disconnect_timeout=int(params.get_param('web3_wallet_connect.auto_disconnect_timeout', 30)),
            default_gas_price_strategy=params.get_param('web3_wallet_connect.default_gas_price_strategy', 'legacy')
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        
        params.set_param('web3_wallet_connect.balance_update_interval', self.balance_update_interval)
        params.set_param('web3_wallet_connect.network_check_interval', self.network_check_interval)
        params.set_param('web3_wallet_connect.auto_disconnect_timeout', self.auto_disconnect_timeout)
        params.set_param('web3_wallet_connect.default_gas_price_strategy', self.default_gas_price_strategy)

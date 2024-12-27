from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Web3Network(models.Model):
    _name = 'web3.network'
    _description = 'Web3 Network'
    _order = 'chain_id'

    name = fields.Char(string='Network Name', required=True)
    chain_id = fields.Integer(string='Chain ID', required=True)
    currency_symbol = fields.Char(string='Currency Symbol', required=True)
    rpc_url = fields.Char(string='RPC URL', required=True)
    explorer_url = fields.Char(string='Explorer URL', required=True)
    is_active = fields.Boolean(string='Active', default=True)
    wallet_ids = fields.One2many('web3.wallet', 'network_id', string='Wallets')

    _sql_constraints = [
        ('unique_chain_id', 'unique(chain_id)', 'Chain ID must be unique!')
    ]

    @api.constrains('rpc_url')
    def _check_rpc_url(self):
        for record in self:
            if not record.rpc_url.startswith(('http://', 'https://', 'ws://', 'wss://')):
                raise ValidationError(_('RPC URL must start with http://, https://, ws:// or wss://'))

    @api.constrains('explorer_url')
    def _check_explorer_url(self):
        for record in self:
            if not record.explorer_url.startswith(('http://', 'https://')):
                raise ValidationError(_('Explorer URL must start with http:// or https://'))

    def test_connection(self):
        """Test RPC connection to the network"""
        self.ensure_one()
        try:
            from web3 import Web3
            if self.rpc_url.startswith(('ws://', 'wss://')):
                provider = Web3.WebsocketProvider(self.rpc_url)
            else:
                provider = Web3.HTTPProvider(self.rpc_url)
                
            w3 = Web3(provider)
            is_connected = w3.is_connected()
            if is_connected:
                block_number = w3.eth.block_number
                _logger.info(f"Successfully connected to {self.name}. Current block: {block_number}")
            return is_connected
        except Exception as e:
            _logger.error(f"Failed to connect to {self.name}: {str(e)}")
            return False

    def get_web3(self):
        """Get Web3 instance for this network"""
        self.ensure_one()
        from web3 import Web3
        if self.rpc_url.startswith(('ws://', 'wss://')):
            provider = Web3.WebsocketProvider(self.rpc_url)
        else:
            provider = Web3.HTTPProvider(self.rpc_url)
        return Web3(provider)

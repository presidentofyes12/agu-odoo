from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from web3 import Web3
import json
import logging

_logger = logging.getLogger(__name__)

class WalletConfig(models.Model):
    _name = 'wallet.config'
    _description = 'Wallet Configuration'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    network_id = fields.Selection([
        # Mainnets
        ('1', 'Ethereum Mainnet'),
        ('369', 'PulseChain'),
        ('137', 'Polygon Mainnet'),
        ('56', 'BSC Mainnet'),
        ('42161', 'Arbitrum One'),
        # Testnets
        ('11155111', 'Sepolia Testnet'),
        ('80001', 'Polygon Mumbai'),
        ('97', 'BSC Testnet'),
        ('421613', 'Arbitrum Goerli'),
    ], required=True, tracking=True)

    rpc_url = fields.Char('RPC URL', required=True, tracking=True)
    network_currency = fields.Char(compute='_compute_network_info', store=True)
    explorer_url = fields.Char(compute='_compute_network_info', store=True)
    active = fields.Boolean(default=True, tracking=True)
    
    # Web3 specific settings
    gas_limit = fields.Integer('Gas Limit', default=8000000)
    gas_price_strategy = fields.Selection([
        ('legacy', 'Legacy'),
        ('eip1559', 'EIP-1559')
    ], default='legacy', required=True)

    _sql_constraints = [
        ('network_unique', 'UNIQUE(network_id, active)',
         'Only one active configuration per network is allowed!')
    ]

    def get_web3_connection(self):
        """Establish Web3 connection using configuration"""
        self.ensure_one()
        try:
            provider = Web3.HTTPProvider(self.rpc_url)
            web3 = Web3(provider)
            if not web3.is_connected():
                raise UserError("Could not connect to blockchain node")
            return web3
        except Exception as e:
            raise UserError(f"Failed to establish Web3 connection: {str(e)}")

    def get_gas_price(self):
        """Get current gas price based on strategy"""
        self.ensure_one()
        web3 = self.get_web3_connection()
        
        if self.gas_price_strategy == 'eip1559':
            block = web3.eth.get_block('latest')
            return {
                'maxFeePerGas': block['baseFeePerGas'] * 2,
                'maxPriorityFeePerGas': web3.eth.max_priority_fee
            }
        return {'gasPrice': web3.eth.gas_price}

    @api.model
    def _check_network_status(self):
        """Cron job to check network status"""
        configs = self.search([('active', '=', True)])
        for config in configs:
            try:
                web3 = config.get_web3_connection()
                web3.eth.get_block_number()
            except Exception as e:
                _logger.error(f"Network check failed for {config.name}: {str(e)}")

    @api.depends('network_id')
    def _compute_network_info(self):
        """Compute network currency and explorer URL"""
        currencies = {
            '1': 'ETH', '369': 'PLS', '137': 'MATIC',
            '56': 'BNB', '42161': 'ETH'
        }
        explorers = {
            '1': 'https://etherscan.io',
            '369': 'https://otter.pulsechain.com',
            '137': 'https://polygonscan.com',
            '56': 'https://bscscan.com',
            '42161': 'https://arbiscan.io'
        }
        
        for record in self:
            record.network_currency = currencies.get(record.network_id, 'ETH')
            record.explorer_url = explorers.get(record.network_id, '')

    def test_connection(self):
        """Test blockchain node connection"""
        self.ensure_one()
        try:
            web3 = self.get_web3_connection()
            block_number = web3.eth.block_number
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test',
                    'message': f'Successfully connected. Latest block: {block_number}',
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test',
                    'message': f'Connection failed: {str(e)}',
                    'type': 'danger',
                }
            }

    @api.onchange('network_id')
    def _onchange_network_id(self):
        """Update RPC URL when network changes"""
        if self.network_id:
            rpc_urls = {
                '1': 'https://mainnet.infura.io/v3/YOUR-PROJECT-ID',
                '369': 'https://rpc.pulsechain.com',
                '137': 'https://polygon-rpc.com',
                '56': 'https://bsc-dataseed.binance.org',
                '42161': 'https://arb1.arbitrum.io/rpc'
            }
            self.rpc_url = rpc_urls.get(self.network_id, '')

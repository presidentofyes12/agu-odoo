from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from web3 import Web3
import json
import logging

_logger = logging.getLogger(__name__)

class WalletConfig(models.Model):
    _name = 'wallet.config'
    _description = 'Wallet Network Configuration'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    network_id = fields.Selection([
        ('1', 'Ethereum Mainnet'),
        ('11155111', 'Sepolia Testnet'),
        ('137', 'Polygon'),
        ('80001', 'Mumbai Testnet'),
        ('369', 'PulseChain'),
        ('943', 'PulseChain Testnet'),
    ], required=True, tracking=True, string='Network')

    rpc_url = fields.Char('RPC URL', required=True, tracking=True)
    network_currency = fields.Char(compute='_compute_network_info', store=True)
    explorer_url = fields.Char(compute='_compute_network_info', store=True)
    gas_limit = fields.Integer('Gas Limit', default=21000)
    gas_price_strategy = fields.Selection([
        ('legacy', 'Legacy'),
        ('eip1559', 'EIP-1559')
    ], default='legacy', required=True)
    
    # Additional fields
    gas_price_multiplier = fields.Float('Gas Price Multiplier', default=1.1)
    max_gas_price = fields.Integer('Max Gas Price (Gwei)', default=500)
    confirmation_blocks = fields.Integer('Confirmation Blocks', default=12)
    active = fields.Boolean(default=True, tracking=True)
    
    # Technical fields
    last_block_number = fields.Integer('Last Block Number', readonly=True)
    last_sync_time = fields.Datetime('Last Sync Time', readonly=True)
    sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('syncing', 'Syncing'),
        ('error', 'Error')
    ], default='synced', readonly=True)

    _sql_constraints = [
        ('unique_active_network', 
         'UNIQUE(network_id, active)',
         'Only one configuration can be active per network!')
    ]

    @api.depends('network_id')
    def _compute_network_info(self):
        currencies = {
            '1': 'ETH',
            '11155111': 'SEP',
            '137': 'MATIC',
            '80001': 'tMATIC',
            '369': 'PLS',
            '943': 'tPLS',
        }
        explorers = {
            '1': 'https://etherscan.io',
            '11155111': 'https://sepolia.etherscan.io',
            '137': 'https://polygonscan.com',
            '80001': 'https://mumbai.polygonscan.com',
            '369': 'https://scan.pulsechain.com',
            '943': 'https://scan.v3.testnet.pulsechain.com',
        }
        for record in self:
            record.network_currency = currencies.get(record.network_id, 'ETH')
            record.explorer_url = explorers.get(record.network_id, '')

    def get_web3_connection(self):
        """Get Web3 connection using current configuration"""
        self.ensure_one()
        try:
            provider = Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 60})
            web3 = Web3(provider)
            if not web3.is_connected():
                raise UserError("Could not connect to blockchain node")
            return web3
        except Exception as e:
            raise UserError(f"Failed to establish Web3 connection: {str(e)}")

    def get_gas_price(self):
        """Get current gas price based on strategy"""
        web3 = self.get_web3_connection()
        if self.gas_price_strategy == 'eip1559':
            block = web3.eth.get_block('latest')
            base_fee = block['baseFeePerGas']
            priority_fee = web3.eth.max_priority_fee
            max_fee = int(base_fee * self.gas_price_multiplier) + priority_fee
            return {
                'maxFeePerGas': min(max_fee, web3.to_wei(self.max_gas_price, 'gwei')),
                'maxPriorityFeePerGas': priority_fee
            }
        else:
            gas_price = int(web3.eth.gas_price * self.gas_price_multiplier)
            return {
                'gasPrice': min(gas_price, web3.to_wei(self.max_gas_price, 'gwei'))
            }

    def test_connection(self):
        """Test connection to blockchain node"""
        self.ensure_one()
        try:
            web3 = self.get_web3_connection()
            block_number = web3.eth.block_number
            gas_price = web3.from_wei(web3.eth.gas_price, 'gwei')
            
            self.write({
                'last_block_number': block_number,
                'last_sync_time': fields.Datetime.now(),
                'sync_status': 'synced'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': f'Connected to network at block {block_number}. '
                              f'Gas price: {gas_price:.2f} Gwei',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.sync_status = 'error'
            raise UserError(f"Connection test failed: {str(e)}")

    def update_gas_prices(self):
        """Cron job to update gas prices"""
        configs = self.search([('active', '=', True)])
        for config in configs:
            try:
                web3 = config.get_web3_connection()
                gas_price = web3.eth.gas_price
                _logger.info(f"Updated gas price for {config.name}: "
                           f"{web3.from_wei(gas_price, 'gwei')} Gwei")
            except Exception as e:
                _logger.error(f"Failed to update gas price for {config.name}: {str(e)}")

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from web3 import Web3
import json
import logging

_logger = logging.getLogger(__name__)

class DAOConfiguration(models.Model):
    _name = 'dao.config'
    _description = 'DAO Configuration'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    network_id = fields.Selection([
        # Mainnets
        ('1', 'Ethereum Mainnet'),
        ('137', 'Polygon Mainnet'),
        ('56', 'BSC Mainnet'),
        ('42161', 'Arbitrum One'),
        ('10', 'Optimism'),
        ('43114', 'Avalanche C-Chain'),
        # Testnets
        ('11155111', 'Sepolia Testnet'),
        ('80001', 'Polygon Mumbai'),
        ('97', 'BSC Testnet'),
        ('421613', 'Arbitrum Goerli'),
        ('420', 'Optimism Goerli'),
        ('43113', 'Avalanche Fuji'),
    ], required=True, tracking=True, string='Network')

    rpc_url = fields.Char('RPC URL', required=True, tracking=True)
    contract_address = fields.Char('Smart Contract Address', required=True, tracking=True)
    contract_abi = fields.Text('Contract ABI', required=True)
    gas_limit = fields.Integer('Gas Limit', default=8000000)
    active = fields.Boolean(default=True, tracking=True)
    
    # Add computed fields for network information
    network_currency = fields.Char(string='Network Currency', compute='_compute_network_info', store=True)
    explorer_url = fields.Char(string='Explorer URL', compute='_compute_network_info', store=True)

    _sql_constraints = [
        ('active_unique', 'UNIQUE(active)', 
         'Only one configuration can be active at a time!')
    ]

    gas_price_strategy = fields.Selection([
        ('legacy', 'Legacy'),
        ('eip1559', 'EIP-1559')
    ], string='Gas Price Strategy', required=True, default='legacy')  # Add default value

    def get_web3_connection(self):
        """Get Web3 connection using current configuration"""
        if not self:
            # If called as a model method, find active config
            config = self.search([('active', '=', True)], limit=1)
            if not config:
                raise UserError("No active DAO configuration found")
        else:
            config = self
    
        try:
            provider = Web3.HTTPProvider(config.rpc_url)
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
            return {
                'maxFeePerGas': block['baseFeePerGas'] * 2,
                'maxPriorityFeePerGas': web3.eth.max_priority_fee
            }
        return {'gasPrice': web3.eth.gas_price}

    # In dao_config.py
    def update_gas_prices(self):
        """Update current gas prices from network"""
        web3 = self.get_web3_connection()
        # Implementation here
        pass

    def sync_blockchain_data(self):
        """Synchronize blockchain data with Odoo"""
        # Implementation here
        pass

    @api.model
    def get_contract(self):
        """Get contract instance using active configuration"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValueError("No active DAO configuration found")
        
        web3 = self.get_web3_connection()
        contract_abi = json.loads(config.contract_abi)
        return web3.eth.contract(
            address=config.contract_address,
            abi=contract_abi
        )

    # Add to dao_config.py
    def call_contract_method(self, method_name, *args, **kwargs):
        """Generic contract method caller with error handling"""
        contract = self.get_contract()
        try:
            method = getattr(contract.functions, method_name)
            return method(*args, **kwargs).call()
        except Exception as e:
            raise UserError(f"Contract call failed: {str(e)}")

    #@api.multi
    def test_connection(self):
        """Test the connection to the blockchain node"""
        self.ensure_one()
        try:
            web3 = self.get_web3_connection()
            if web3.is_connected():
                status = 'success'
                message = 'Successfully connected to blockchain node'
            else:
                status = 'warning'
                message = 'Could not establish connection'
        except Exception as e:
            status = 'danger'
            message = f'Connection failed: {str(e)}'
    
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Test',
                'message': message,
                'type': status,
                'sticky': False,
            }
        }

    def send_contract_transaction(self, method_name, *args, **kwargs):
        """Generic contract transaction sender"""
        contract = self.get_contract()
        try:
            method = getattr(contract.functions, method_name)
            gas_params = self.get_gas_price()
            tx_params = {
                'from': kwargs.pop('from_address'),
                **gas_params
            }
            return method(*args, **kwargs).transact(tx_params)
        except Exception as e:
            raise UserError(f"Transaction failed: {str(e)}")

    @api.constrains('contract_abi')
    def _check_contract_abi(self):
        """Validate contract ABI JSON format"""
        for record in self:
            if record.contract_abi:
                try:
                    # Try to parse the ABI as JSON
                    abi = json.loads(record.contract_abi)
                    # Verify it's a list
                    if not isinstance(abi, list):
                        raise ValidationError("Contract ABI must be a JSON array")
                    # Basic ABI structure validation
                    for item in abi:
                        if not isinstance(item, dict):
                            raise ValidationError("Invalid ABI format: each entry must be an object")
                        if 'type' not in item:
                            raise ValidationError("Invalid ABI format: missing 'type' field in entry")
                except json.JSONDecodeError:
                    raise ValidationError("Contract ABI must be valid JSON")
                except Exception as e:
                    raise ValidationError(f"Invalid Contract ABI format: {str(e)}")
    
    # Add a helper method to format ABI
    def format_abi(self):
        """Format the ABI JSON for better readability"""
        if self.contract_abi:
            try:
                abi = json.loads(self.contract_abi)
                self.contract_abi = json.dumps(abi, indent=2)
            except Exception:
                pass  # If formatting fails, keep original

    def get_network_currency(self):
        """Get native currency symbol for selected network"""
        currencies = {
            # Mainnets
            '1': 'ETH',
            '137': 'MATIC',
            '56': 'BNB',
            '42161': 'ETH',
            '10': 'ETH',
            '43114': 'AVAX',
            # Testnets
            '11155111': 'SEP',
            '80001': 'tMATIC',
            '97': 'tBNB',
            '421613': 'AGOR',
            '420': 'ETH',
            '43113': 'AVAX',
        }
        return currencies.get(self.network_id, 'ETH')

    @api.depends('network_id')
    def _compute_network_info(self):
        """Compute network currency and explorer URL"""
        currencies = {
            # Mainnets
            '1': 'ETH',
            '137': 'MATIC',
            '56': 'BNB',
            '42161': 'ETH',
            '10': 'ETH',
            '43114': 'AVAX',
            # Testnets
            '11155111': 'SEP',
            '80001': 'tMATIC',
            '97': 'tBNB',
            '421613': 'AGOR',
            '420': 'ETH',
            '43113': 'AVAX',
        }
        
        explorers = {
            # Mainnets
            '1': 'https://etherscan.io',
            '137': 'https://polygonscan.com',
            '56': 'https://bscscan.com',
            '42161': 'https://arbiscan.io',
            '10': 'https://optimistic.etherscan.io',
            '43114': 'https://snowtrace.io',
            # Testnets
            '11155111': 'https://sepolia.etherscan.io',
            '80001': 'https://mumbai.polygonscan.com',
            '97': 'https://testnet.bscscan.com',
            '421613': 'https://goerli.arbiscan.io',
            '420': 'https://goerli-optimism.etherscan.io',
            '43113': 'https://testnet.snowtrace.io',
        }
        
        for record in self:
            record.network_currency = currencies.get(record.network_id, 'ETH')
            record.explorer_url = explorers.get(record.network_id, '')

    def get_explorer_url(self):
        """Get block explorer URL for selected network"""
        explorers = {
            # Mainnets
            '1': 'https://etherscan.io',
            '137': 'https://polygonscan.com',
            '56': 'https://bscscan.com',
            '42161': 'https://arbiscan.io',
            '10': 'https://optimistic.etherscan.io',
            '43114': 'https://snowtrace.io',
            # Testnets
            '11155111': 'https://sepolia.etherscan.io',
            '80001': 'https://mumbai.polygonscan.com',
            '97': 'https://testnet.bscscan.com',
            '421613': 'https://goerli.arbiscan.io',
            '420': 'https://goerli-optimism.etherscan.io',
            '43113': 'https://testnet.snowtrace.io',
        }
        return explorers.get(self.network_id, '')

    @api.onchange('network_id')
    def _onchange_network_id(self):
        """Provide default RPC URL based on selected network"""
        if self.network_id:
            rpc_urls = {
                # Mainnets
                '1': 'https://mainnet.infura.io/v3/YOUR-PROJECT-ID',
                '137': 'https://polygon-rpc.com',
                '56': 'https://bsc-dataseed.binance.org',
                '42161': 'https://arb1.arbitrum.io/rpc',
                '10': 'https://mainnet.optimism.io',
                '43114': 'https://api.avax.network/ext/bc/C/rpc',
                # Testnets
                '11155111': 'https://sepolia.infura.io/v3/YOUR-PROJECT-ID',
                '80001': 'https://rpc-mumbai.maticvigil.com',
                '97': 'https://data-seed-prebsc-1-s1.binance.org:8545',
                '421613': 'https://goerli-rollup.arbitrum.io/rpc',
                '420': 'https://goerli.optimism.io',
                '43113': 'https://api.avax-test.network/ext/bc/C/rpc',
            }
            self.rpc_url = rpc_urls.get(self.network_id, '')

    @api.onchange('contract_abi')
    def _onchange_contract_abi(self):
        """Format ABI when it changes"""
        self.format_abi()
    
class DAOEventFilter(models.Model):
    _name = 'dao.event.filter'
    
    config_id = fields.Many2one('dao.config', required=True)
    event_name = fields.Char(required=True)
    active = fields.Boolean(default=True)

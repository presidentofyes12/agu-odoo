from odoo import http, _
from odoo.http import request
import json
import logging
from web3 import Web3

_logger = logging.getLogger(__name__)

class Web3WalletController(http.Controller):
    
    @http.route('/web3_wallet/connect', type='json', auth="user")
    def connect_wallet(self, address, chain_id):
        """Connect a Web3 wallet"""
        try:
            # Validate the address
            if not Web3.is_address(address):
                return {'error': _('Invalid wallet address')}

            # Get the network
            network = request.env['web3.network'].sudo().search([('chain_id', '=', chain_id)], limit=1)
            if not network:
                return {'error': _('Unsupported network')}

            # Create or get the wallet
            wallet = request.env['web3.wallet'].sudo().search([
                ('address', '=', address),
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not wallet:
                wallet = request.env['web3.wallet'].sudo().create({
                    'name': f'Wallet {address[:8]}',
                    'address': address,
                    'user_id': request.env.user.id,
                    'network_id': network.id,
                })
            
            wallet.action_connect_wallet()
            
            return {
                'success': True,
                'wallet_id': wallet.id,
                'address': wallet.address,
                'balance': wallet.balance,
                'network': {
                    'name': network.name,
                    'chain_id': network.chain_id,
                    'currency_symbol': network.currency_symbol
                }
            }
        except Exception as e:
            _logger.error(f"Error connecting wallet: {str(e)}")
            return {'error': _('Failed to connect wallet')}

    @http.route('/web3_wallet/disconnect', type='json', auth="user")
    def disconnect_wallet(self, wallet_id):
        """Disconnect a Web3 wallet"""
        try:
            wallet = request.env['web3.wallet'].sudo().browse(wallet_id)
            if wallet.exists() and wallet.user_id.id == request.env.user.id:
                wallet.action_disconnect_wallet()
                return {'success': True}
            return {'error': _('Wallet not found')}
        except Exception as e:
            _logger.error(f"Error disconnecting wallet: {str(e)}")
            return {'error': _('Failed to disconnect wallet')}

    @http.route('/web3_wallet/get_networks', type='json', auth="user")
    def get_networks(self):
        """Get list of supported networks"""
        networks = request.env['web3.network'].sudo().search([('is_active', '=', True)])
        return {
            'networks': [{
                'id': network.id,
                'name': network.name,
                'chain_id': network.chain_id,
                'currency_symbol': network.currency_symbol,
                'explorer_url': network.explorer_url
            } for network in networks]
        }

    @http.route('/web3_wallet/get_transactions', type='json', auth="user")
    def get_transactions(self, wallet_id, limit=20):
        """Get transaction history for a wallet"""
        try:
            wallet = request.env['web3.wallet'].sudo().browse(wallet_id)
            if not wallet.exists() or wallet.user_id.id != request.env.user.id:
                return {'error': _('Wallet not found')}

            transactions = wallet.transaction_ids.sorted(key='timestamp', reverse=True)[:limit]
            
            return {
                'success': True,
                'transactions': [{
                    'hash': tx.tx_hash,
                    'from_address': tx.from_address,
                    'to_address': tx.to_address,
                    'value': tx.value,
                    'timestamp': tx.timestamp,
                    'status': tx.status,
                    'type': 'sent' if tx.from_address.lower() == wallet.address.lower() else 'received'
                } for tx in transactions]
            }
        except Exception as e:
            _logger.error(f"Error fetching transactions: {str(e)}")
            return {'error': _('Failed to fetch transactions')}

    @http.route('/web3_wallet/estimate_gas', type='json', auth="user")
    def estimate_gas(self, wallet_id, to_address, amount):
        """Estimate gas for a transaction"""
        try:
            wallet = request.env['web3.wallet'].sudo().browse(wallet_id)
            if not wallet.exists() or wallet.user_id.id != request.env.user.id:
                return {'error': _('Wallet not found')}

            w3 = Web3(Web3.HTTPProvider(wallet.network_id.rpc_url))
            
            # Estimate gas for a standard ETH transfer
            gas_estimate = 21000  # Standard ETH transfer
            gas_price = w3.eth.gas_price
            
            return {
                'success': True,
                'gas_estimate': gas_estimate,
                'gas_price': w3.from_wei(gas_price, 'gwei'),
                'total_gas_cost': w3.from_wei(gas_estimate * gas_price, 'ether')
            }
        except Exception as e:
            _logger.error(f"Error estimating gas: {str(e)}")
            return {'error': _('Failed to estimate gas')}

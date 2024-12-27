from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import logging
import json

_logger = logging.getLogger(__name__)

class WalletController(http.Controller):
    @http.route('/web3_wallet/create', type='json', auth='user')
    def create_wallet(self, **kwargs):
        """Create new Ethereum wallet"""
        try:
            result = request.env['res.users'].create_web3_wallet()
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            _logger.error("Wallet creation failed: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/web3_wallet/balance/<string:address>', type='json', auth='user')
    def get_balance(self, address, **kwargs):
        """Get wallet balance"""
        try:
            wallet = request.env['wallet.config'].get_web3_connection()
            balance = wallet.eth.get_balance(address)
            return {
                'success': True,
                'balance': wallet.from_wei(balance, 'ether'),
                'address': address
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/web3_wallet/transaction/estimate', type='json', auth='user')
    def estimate_transaction(self, to_address, amount, **kwargs):
        """Estimate transaction gas cost"""
        try:
            result = request.env['wallet.transaction'].estimate_transaction(
                to_address, float(amount))
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/web3_wallet/transaction/send', type='json', auth='user')
    def send_transaction(self, **post):
        """Send transaction"""
        try:
            required_fields = ['to_address', 'amount', 'gas_price', 'gas_limit']
            if not all(field in post for field in required_fields):
                raise UserError("Missing required transaction parameters")

            transaction = request.env['wallet.transaction'].create({
                'to_address': post['to_address'],
                'value': float(post['amount']),
                'gas_price': float(post['gas_price']),
                'gas_limit': int(post['gas_limit']),
                'user_id': request.env.user.id,
            })
            
            result = transaction.submit_transaction()
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            _logger.error("Transaction failed: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/web3_wallet/transaction/<string:tx_hash>/status', type='json', auth='user')
    def get_transaction_status(self, tx_hash, **kwargs):
        """Get transaction status"""
        try:
            transaction = request.env['wallet.transaction'].search([
                ('transaction_hash', '=', tx_hash)
            ], limit=1)
            
            if not transaction:
                return {
                    'success': False,
                    'error': 'Transaction not found'
                }
                
            return {
                'success': True,
                'data': {
                    'status': transaction.status,
                    'block_number': transaction.block_number,
                    'gas_used': transaction.gas_used,
                    'timestamp': transaction.timestamp,
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/web3_wallet/networks', type='json', auth='user')
    def get_networks(self):
        """Get available networks"""
        try:
            networks = request.env['wallet.config'].search_read(
                domain=[('active', '=', True)],
                fields=['name', 'network_id', 'rpc_url', 'network_currency']
            )
            return {
                'success': True,
                'data': networks
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import json
import logging

_logger = logging.getLogger(__name__)

class WalletController(http.Controller):
    @http.route('/web3_wallet_connect/update_connection', type='json', auth='user')
    def update_connection(self, account, chain_id=None, provider_type='web3'):
        """Update user's wallet connection status"""
        try:
            user = request.env.user
            vals = {
                'is_wallet_connected': bool(account),
                'last_connection_type': provider_type,
            }
            
            if provider_type == 'web3':
                vals.update({
                    'eth_address': account,
                    'current_chain_id': chain_id
                })
            elif provider_type == 'nostr':
                vals.update({
                    'nostr_public_key': account
                })
                
            user.write(vals)
            return {'success': True}
        except Exception as e:
            _logger.error("Wallet connection update failed: %s", str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/web3_wallet_connect/get_network_config', type='json', auth='user')
    def get_network_config(self, chain_id):
        """Get network configuration for specified chain ID"""
        try:
            config = request.env['wallet.config'].sudo().search([
                ('network_id', '=', str(chain_id)),
                ('active', '=', True)
            ], limit=1)
            
            if not config:
                return {'success': False, 'error': 'Network not configured'}
                
            return {
                'success': True,
                'data': {
                    'name': config.name,
                    'rpc_url': config.rpc_url,
                    'currency': config.network_currency,
                    'explorer_url': config.explorer_url
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/web3_wallet_connect/import_wallet', type='json', auth='user')
    def import_wallet(self, wallet_data):
        """Handle wallet import request"""
        try:
            wizard = request.env['wallet.import.wizard'].create({
                'user_id': request.env.user.id,
                **wallet_data
            })
            result = wizard.action_import()
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error("Wallet import failed: %s", str(e))
            return {'success': False, 'error': str(e)}

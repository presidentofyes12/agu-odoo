from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import json
import logging

_logger = logging.getLogger(__name__)

class DAOController(http.Controller):
    @http.route('/dao/wallet/create', type='json', auth='user')
    def create_wallet(self):
        """API endpoint to create new wallet"""
        return request.env['res.users'].create_wallet()

    @http.route('/dao/transaction/status/<string:tx_hash>', type='json', auth='user')
    def get_transaction_status(self, tx_hash):
        """API endpoint to check transaction status"""
        transaction = request.env['dao.transaction'].search([
            ('transaction_hash', '=', tx_hash)
        ], limit=1)
        return {'status': transaction.status if transaction else 'not_found'}

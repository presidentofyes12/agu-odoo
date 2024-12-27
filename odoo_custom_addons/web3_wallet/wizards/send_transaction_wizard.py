from odoo import models, fields, api, _
from odoo.exceptions import UserError
from web3 import Web3
import logging

_logger = logging.getLogger(__name__)

class SendTransactionWizard(models.TransientModel):
    _name = 'send.transaction.wizard'
    _description = 'Send Web3 Transaction'

    wallet_id = fields.Many2one('web3.wallet', string='Wallet', required=True)
    from_address = fields.Char(string='From Address', readonly=True)
    to_address = fields.Char(string='To Address', required=True)
    amount = fields.Float(string='Amount', required=True, digits=(18, 8))
    network_id = fields.Many2one('web3.network', string='Network', required=True)
    estimated_gas = fields.Float(string='Estimated Gas (Gwei)', compute='_compute_estimated_gas')
    gas_price = fields.Float(string='Gas Price (Gwei)', compute='_compute_estimated_gas')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost')
    currency_symbol = fields.Char(related='network_id.currency_symbol')

    @api.depends('to_address', 'amount', 'network_id')
    def _compute_estimated_gas(self):
        for record in self:
            try:
                if record.to_address and record.amount and record.network_id:
                    # Standard ETH transfer gas
                    record.estimated_gas = 21000
                    # Get gas price from network data
                    w3 = Web3(Web3.HTTPProvider(record.network_id.rpc_url))
                    record.gas_price = float(w3.from_wei(w3.eth.gas_price, 'gwei'))
                else:
                    record.estimated_gas = 0
                    record.gas_price = 0
            except Exception as e:
                _logger.error(f"Error computing gas estimate: {str(e)}")
                record.estimated_gas = 0
                record.gas_price = 0

    @api.depends('amount', 'estimated_gas', 'gas_price')
    def _compute_total_cost(self):
        for record in self:
            gas_cost = (record.estimated_gas * record.gas_price) / 1e9  # Convert from Gwei to ETH
            record.total_cost = record.amount + gas_cost

    @api.model
    def default_get(self, fields):
        res = super(SendTransactionWizard, self).default_get(fields)
        if self._context.get('active_model') == 'web3.wallet':
            wallet = self.env['web3.wallet'].browse(self._context.get('active_id'))
            if wallet:
                res.update({
                    'wallet_id': wallet.id,
                    'from_address': wallet.address,
                    'network_id': wallet.network_id.id,
                })
        return res

    def action_send_transaction(self):
        """Create a pending transaction record and initiate MetaMask transaction"""
        self.ensure_one()
        if not Web3.is_address(self.to_address):
            raise UserError(_("Invalid destination address"))

        if self.amount <= 0:
            raise UserError(_("Amount must be greater than 0"))

        if self.wallet_id.balance < self.total_cost:
            raise UserError(_("Insufficient balance for transaction"))

        try:
            # Create a pending transaction record
            transaction = self.env['web3.transaction'].create({
                'wallet_id': self.wallet_id.id,
                'from_address': self.from_address,
                'to_address': self.to_address,
                'value': self.amount,
                'network_id': self.network_id.id,
                'status': 'pending',
                'gas_price': self.gas_price,
                'gas_used': self.estimated_gas,
                'tx_hash': 'pending'  # Will be updated after MetaMask confirms
            })

            # Return the client action to handle MetaMask interaction
            return {
                'type': 'ir.actions.client',
                'tag': 'web3_send_transaction',
                'target': 'new',
                'params': {
                    'transaction_id': transaction.id,
                    'to_address': self.to_address,
                    'value': self.amount,
                    'chain_id': self.network_id.chain_id,
                }
            }
        except Exception as e:
            _logger.error(f"Error preparing transaction: {str(e)}")
            raise UserError(_("Failed to prepare transaction: %s") % str(e))

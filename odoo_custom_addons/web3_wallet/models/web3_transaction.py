from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Web3Transaction(models.Model):
    _name = 'web3.transaction'
    _description = 'Web3 Transaction'
    _order = 'timestamp desc, id desc'

    wallet_id = fields.Many2one('web3.wallet', string='Wallet', required=True, ondelete='cascade')
    network_id = fields.Many2one('web3.network', string='Network', required=True)
    tx_hash = fields.Char(string='Transaction Hash', required=True, default='pending')
    from_address = fields.Char(string='From Address', required=True)
    to_address = fields.Char(string='To Address')
    value = fields.Float(string='Value', digits=(18,8), required=True)
    gas_price = fields.Float(string='Gas Price (Gwei)', digits=(18,2))
    gas_used = fields.Integer(string='Gas Used')
    timestamp = fields.Datetime(string='Timestamp')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed')
    ], string='Status', default='pending', required=True)
    currency_symbol = fields.Char(related='network_id.currency_symbol', string='Currency')

    _sql_constraints = [
        ('unique_tx_hash_per_wallet', 'unique(wallet_id,tx_hash)', 
         'Transaction hash must be unique per wallet!')
    ]

    @api.constrains('from_address', 'to_address')
    def _check_addresses(self):
        from web3 import Web3
        for tx in self:
            if not Web3.is_address(tx.from_address):
                raise ValidationError(_('Invalid sender address format'))
            if tx.to_address and not Web3.is_address(tx.to_address):
                raise ValidationError(_('Invalid recipient address format'))

    def action_view_on_explorer(self):
        """Open transaction in blockchain explorer"""
        self.ensure_one()
        if not self.network_id.explorer_url:
            raise ValidationError(_('No explorer URL configured for this network'))
        
        explorer_url = f"{self.network_id.explorer_url}/tx/{self.tx_hash}"
        return {
            'type': 'ir.actions.act_url',
            'url': explorer_url,
            'target': 'new'
        }

    def action_check_status(self):
        """Check transaction status on blockchain"""
        self.ensure_one()
        try:
            web3 = self.network_id.get_web3()
            receipt = web3.eth.get_transaction_receipt(self.tx_hash)
            
            if receipt:
                self.status = 'confirmed' if receipt['status'] == 1 else 'failed'
                if 'gasUsed' in receipt:
                    self.gas_used = receipt['gasUsed']
                    
            return True
        except Exception as e:
            _logger.error(f"Failed to check transaction status: {str(e)}")
            return False

    @api.model
    def cron_update_pending_transactions(self):
        """Cron job to update pending transaction statuses"""
        pending_txs = self.search([('status', '=', 'pending')])
        for tx in pending_txs:
            try:
                tx.action_check_status()
            except Exception as e:
                _logger.error(f"Failed to update transaction {tx.tx_hash}: {str(e)}")

    # Add this constraint instead of the SQL constraint
    @api.constrains('tx_hash', 'status')
    def _check_tx_hash(self):
        for record in self:
            if record.status != 'pending' and record.tx_hash == 'pending':
                raise ValidationError(_('Transaction hash is required for non-pending transactions'))

    def get_transaction_fees(self):
        """Calculate transaction fees in native currency"""
        self.ensure_one()
        if self.gas_price and self.gas_used:
            fee_in_gwei = self.gas_price * self.gas_used
            fee_in_eth = fee_in_gwei / 1e9  # Convert from Gwei to ETH
            return {
                'amount': fee_in_eth,
                'currency': self.currency_symbol
            }
        return False

    def name_get(self):
        return [(tx.id, f"{tx.tx_hash[:10]}... ({tx.value} {tx.currency_symbol})") 
                for tx in self]

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from eth_account.messages import encode_defunct
import json
import logging

_logger = logging.getLogger(__name__)

class WalletTransaction(models.Model):
    _name = 'wallet.transaction'
    _description = 'Wallet Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one('res.users', required=True, readonly=True,
                             default=lambda self: self.env.user)
    from_address = fields.Char('From Address', required=True, tracking=True)
    to_address = fields.Char('To Address', required=True, tracking=True)
    value = fields.Float('Value', digits=(18, 8), required=True, tracking=True)
    gas_price = fields.Float('Gas Price (Gwei)', digits=(18, 2))
    gas_limit = fields.Integer('Gas Limit')
    gas_used = fields.Integer('Gas Used', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    transaction_hash = fields.Char('Transaction Hash', readonly=True)
    block_number = fields.Integer('Block Number', readonly=True)
    block_timestamp = fields.Datetime('Block Timestamp', readonly=True)
    network_id = fields.Many2one('wallet.config', required=True)
    nonce = fields.Integer('Nonce', readonly=True)
    confirmation_blocks = fields.Integer('Confirmations', readonly=True)
    
    # Technical fields
    raw_transaction = fields.Text('Raw Transaction', readonly=True)
    signed_transaction = fields.Text('Signed Transaction', readonly=True)
    error_message = fields.Text('Error Message', readonly=True)

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('wallet.transaction')
        return super().create(vals)

    @api.constrains('value')
    def _check_value(self):
        for record in self:
            if record.value <= 0:
                raise ValidationError("Transaction value must be positive")

    def action_send(self):
        """Send transaction to blockchain"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Only draft transactions can be sent")
        
        try:
            web3 = self.network_id.get_web3_connection()
            # Verify balance
            balance = web3.eth.get_balance(self.from_address)
            total_cost = web3.to_wei(self.value, 'ether') + (self.gas_limit * web3.to_wei(self.gas_price, 'gwei'))
            if balance < total_cost:
                raise UserError("Insufficient balance for transaction")

            # Prepare transaction
            tx_params = {
                'from': self.from_address,
                'to': self.to_address,
                'value': web3.to_wei(self.value, 'ether'),
                'gas': self.gas_limit,
                'gasPrice': web3.to_wei(self.gas_price, 'gwei'),
                'nonce': web3.eth.get_transaction_count(self.from_address),
            }
            
            # Get private key from user
            private_key = self.user_id._get_wallet_private_key()
            if not private_key:
                raise UserError("Private key not available")
            
            # Sign and send transaction
            signed_tx = web3.eth.account.sign_transaction(tx_params, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            self.write({
                'state': 'pending',
                'transaction_hash': web3.to_hex(tx_hash),
                'nonce': tx_params['nonce'],
                'raw_transaction': json.dumps(tx_params),
                'signed_transaction': web3.to_hex(signed_tx.rawTransaction)
            })
            
            return True
            
        except Exception as e:
            self.write({
                'state': 'failed',
                'error_message': str(e)
            })
            raise UserError(f"Transaction failed: {str(e)}")

    def clean_old_transactions(self):
        """Clean old transaction records"""
        # Keep records for last 90 days
        cutoff_date = fields.Datetime.now() - timedelta(days=90)
        old_records = self.search([
            ('create_date', '<', cutoff_date),
            ('state', 'in', ['completed', 'failed', 'cancelled'])
        ])
        
        if old_records:
            _logger.info(f"Cleaning {len(old_records)} old transaction records")
            old_records.unlink()
        
        return True

    def action_cancel(self):
        """Cancel the transaction"""
        self.ensure_one()
        if self.state not in ['draft', 'failed']:
            raise UserError("Only draft or failed transactions can be cancelled")
        
        self.write({
            'state': 'cancelled',
            'error_message': 'Transaction cancelled by user'
        })
        return True

    def action_retry(self):
        """Retry failed transaction with increased gas price"""
        self.ensure_one()
        if self.state != 'failed':
            raise UserError("Only failed transactions can be retried")
        
        # Create new transaction with increased gas price
        new_tx = self.copy({
            'state': 'draft',
            'transaction_hash': False,
            'error_message': False,
            'gas_price': self.gas_price * 1.1  # Increase gas price by 10%
        })
        
        # Open the new transaction form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wallet.transaction',
            'res_id': new_tx.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def update_pending_transactions(self):
        """Update status of pending transactions"""
        pending_txs = self.search([('state', '=', 'pending')])
        for tx in pending_txs:
            try:
                web3 = tx.network_id.get_web3_connection()
                receipt = web3.eth.get_transaction_receipt(tx.transaction_hash)
                if receipt:
                    if receipt['status'] == 1:
                        tx.write({
                            'state': 'completed',
                            'gas_used': receipt['gasUsed'],
                            'block_number': receipt['blockNumber'],
                            'block_timestamp': fields.Datetime.now(),
                            'confirmation_blocks': web3.eth.block_number - receipt['blockNumber']
                        })
                    else:
                        tx.write({
                            'state': 'failed',
                            'error_message': 'Transaction reverted on chain'
                        })
            except Exception as e:
                _logger.error(f"Failed to update transaction {tx.transaction_hash}: {str(e)}")

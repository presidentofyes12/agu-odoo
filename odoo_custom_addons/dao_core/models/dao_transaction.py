# models/dao_transaction.py
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime
from eth_account import Account
import json

_logger = logging.getLogger(__name__)

# In models/dao_transaction.py
class DAOTransaction(models.Model):
    _name = 'dao.transaction'
    _description = 'DAO Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Description', required=True, tracking=True)
    transaction_hash = fields.Char('Transaction Hash', readonly=True, tracking=True)
    # Change from Many2one to Char field and compute it from the related user
    from_address = fields.Char('From Address', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='From User', 
        required=True, default=lambda self: self.env.user,
        domain=[('eth_address', '!=', False)])
    to_address = fields.Char('To Address', required=True,
        states={'draft': [('readonly', False)]}, tracking=True)
    value = fields.Float('Value (ETH)', required=True,
        states={'draft': [('readonly', False)]}, tracking=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True, required=True)
    
    gas_limit = fields.Integer('Gas Limit', states={'draft': [('readonly', False)]})
    gas_price = fields.Float('Gas Price (Gwei)', states={'draft': [('readonly', False)]})
    gas_used = fields.Integer('Gas Used', readonly=True)
    nonce = fields.Integer('Nonce', readonly=True)
    
    is_contract_interaction = fields.Boolean('Is Contract Call', 
        states={'draft': [('readonly', False)]}, default=False)
    contract_method = fields.Char('Contract Method',
        states={'draft': [('readonly', False)]})
    raw_input = fields.Text('Contract Data',
        states={'draft': [('readonly', False)]})
    
    transaction_type = fields.Selection([
        ('private_key', 'Private Key'),
        ('wallet_file', 'Wallet File')
    ], string="Signing Method", default='private_key')
    private_key = fields.Char("Private Key", groups="dao_core.group_dao_admin")
    wallet_file = fields.Binary("Wallet File")
    wallet_password = fields.Char("Wallet Password")
    
    timestamp = fields.Datetime(default=fields.Datetime.now, readonly=True)
    error_message = fields.Text('Error Message', readonly=True)
    eth_balance = fields.Float('Available Balance (ETH)', digits=(18, 8))
    
    estimated_fee = fields.Float('Estimated Fee (ETH)', compute='_compute_estimated_fee', store=True)
    total_amount = fields.Float('Total Amount (ETH)', compute='_compute_total_amount', store=True)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id and self.user_id.eth_address:
            self.from_address = self.user_id.eth_address
            self._compute_eth_balance()

    _sql_constraints = [
        ('hash_unique', 'UNIQUE(transaction_hash)', 
         'Transaction hash must be unique!')
    ]

    # Add new fields for transaction signing
    transaction_type = fields.Selection([
        ('private_key', 'Private Key'),
        ('wallet_file', 'Wallet File')
    ], string="Signing Method", default='private_key', required=True)
    private_key = fields.Char("Private Key", groups="dao_core.group_dao_admin")
    wallet_file = fields.Binary("Wallet File")
    wallet_password = fields.Char("Wallet Password")

    @api.depends('gas_limit', 'gas_price')
    def _compute_estimated_fee(self):
        for record in self:
            if record.gas_limit and record.gas_price:
                record.estimated_fee = (record.gas_limit * record.gas_price * 10**-9)
            else:
                record.estimated_fee = 0

    # Add method to manually refresh balance
    def refresh_balance(self):
        """Manually refresh the ETH balance"""
        self._compute_eth_balance()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.depends('value', 'estimated_fee')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.value + record.estimated_fee

    @api.depends('from_address')
    def _compute_eth_balance(self):
        for record in self:
            try:
                if record.from_address:
                    web3 = self.env['dao.config'].get_web3_connection()
                    balance_wei = web3.eth.get_balance(record.from_address)
                    record.eth_balance = float(web3.from_wei(balance_wei, 'ether'))
                else:
                    record.eth_balance = 0.0
            except Exception as e:
                _logger.error(f"Failed to compute ETH balance: {str(e)}")
                record.eth_balance = 0.0

    @api.onchange('from_address')
    def _onchange_from_address(self):
        if self.from_address:
            config = self.env['dao.config'].search([('active', '=', True)], limit=1)
            if config:
                self.gas_limit = config.gas_limit
                try:
                    web3 = config.get_web3_connection()
                    self.gas_price = web3.from_wei(web3.eth.gas_price, 'gwei')
                except Exception as e:
                    _logger.error(f"Failed to get gas price: {str(e)}")

    @api.constrains('to_address')
    def _check_to_address(self):
        for record in self:
            if record.to_address:
                web3 = self.env['dao.config'].get_web3_connection()
                if not web3.is_address(record.to_address):
                    raise ValidationError("Invalid recipient address format")

    @api.constrains('value', 'eth_balance', 'status')
    def _check_balance(self):
        for record in self:
            if record.status == 'draft' and record.total_amount > record.eth_balance:
                raise ValidationError("Insufficient balance for transaction")

    def action_draft(self):
        """Reset to draft status"""
        return self.write({'status': 'draft'})

    def action_cancel(self):
        """Cancel the transaction"""
        if self.filtered(lambda t: t.status not in ['draft', 'failed']):
            raise UserError("Only draft or failed transactions can be cancelled")
        return self.write({'status': 'cancelled'})

    def submit_transaction_with_key(self):
        """Submit transaction using provided signing method"""
        self.ensure_one()
        if self.status != 'draft':
            raise UserError("Only draft transactions can be submitted")

        try:
            web3 = self.env['dao.config'].get_web3_connection()
            
            if self.total_amount > self.eth_balance:
                raise UserError("Insufficient balance")

            tx_params = {
                'nonce': web3.eth.get_transaction_count(self.from_address),
                'gasPrice': web3.to_wei(self.gas_price, 'gwei'),
                'gas': self.gas_limit or 21000,
                'to': self.to_address,
                'value': web3.to_wei(self.value, 'ether'),
                'data': self.raw_input if self.is_contract_interaction else b''
            }

            if self.transaction_type == 'private_key':
                if not self.private_key:
                    raise UserError("Private key is required")
                try:
                    account = Account.from_key(self.private_key)
                    if account.address.lower() != self.from_address.lower():
                        raise UserError("Private key does not match sender address")
                    signed_tx = web3.eth.account.sign_transaction(tx_params, self.private_key)
                except Exception as e:
                    raise UserError(f"Invalid private key: {str(e)}")

            elif self.transaction_type == 'wallet_file':
                if not self.wallet_file or not self.wallet_password:
                    raise UserError("Wallet file and password are required")
                try:
                    keystore_json = json.loads(self.wallet_file.decode())
                    private_key = web3.eth.account.decrypt(keystore_json, self.wallet_password)
                    account = Account.from_key(private_key)
                    if account.address.lower() != self.from_address.lower():
                        raise UserError("Wallet address does not match sender address")
                    signed_tx = web3.eth.account.sign_transaction(tx_params, private_key)
                except Exception as e:
                    raise UserError(f"Invalid wallet file or password: {str(e)}")

            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            self.write({
                'transaction_hash': web3.to_hex(tx_hash),
                'status': 'pending',
                'private_key': False,
                'wallet_file': False,
                'wallet_password': False
            })

        except Exception as e:
            self.write({
                'status': 'failed',
                'error_message': str(e),
                'private_key': False,
                'wallet_file': False,
                'wallet_password': False
            })
            raise UserError(f"Transaction failed: {str(e)}")

    @api.onchange('transaction_type')
    def _onchange_transaction_type(self):
        """Clear sensitive fields when changing transaction type"""
        self.private_key = False
        self.wallet_file = False
        self.wallet_password = False


    def submit_transaction(self):
        """Submit transaction to blockchain"""
        self.ensure_one()
        if self.status != 'draft':
            raise UserError("Only draft transactions can be submitted")

        try:
            # Validate balance
            if self.total_amount > self.eth_balance:
                raise UserError("Insufficient balance")

            # Get Web3 instance
            web3 = self.env['dao.config'].get_web3_connection()
            
            # Create transaction parameters
            tx_params = {
                'from': self.from_address.eth_address,
                'to': self.to_address,
                'value': web3.to_wei(self.value, 'ether'),
                'gas': self.gas_limit or 21000,
                'gasPrice': web3.to_wei(self.gas_price, 'gwei'),
                'nonce': web3.eth.get_transaction_count(self.from_address.eth_address),
            }

            if self.is_contract_interaction and self.raw_input:
                tx_params['data'] = self.raw_input

            # Send transaction through user's wallet
            tx_hash = self.from_address.send_transaction(
                self.to_address, 
                tx_params['value'],
                tx_params['data'] if self.is_contract_interaction else None
            )
            
            # Update transaction record
            self.write({
                'transaction_hash': tx_hash,
                'status': 'pending',
                'nonce': tx_params['nonce']
            })

        except Exception as e:
            self.write({
                'status': 'failed',
                'error_message': str(e)
            })
            raise UserError(f"Transaction failed: {str(e)}")

    def retry_failed_transaction(self):
        """Retry a failed transaction"""
        self.ensure_one()
        if self.status != 'failed':
            raise UserError("Only failed transactions can be retried")
        
        # Create new transaction with updated gas price
        new_tx = self.copy({
            'status': 'draft',
            'transaction_hash': False,
            'gas_used': False,
            'error_message': False,
            'gas_price': self.gas_price * 1.1  # Increase gas price by 10%
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dao.transaction',
            'res_id': new_tx.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def update_pending_transactions(self):
        """Update status of pending transactions"""
        pending_txs = self.search([('status', '=', 'pending')])
        web3 = self.env['dao.config'].get_web3_connection()
        
        for transaction in pending_txs:
            if transaction.transaction_hash:
                try:
                    receipt = web3.eth.get_transaction_receipt(transaction.transaction_hash)
                    if receipt:
                        status = 'completed' if receipt.status == 1 else 'failed'
                        transaction.write({
                            'status': status,
                            'gas_used': receipt.gasUsed,
                            'error_message': 'Transaction failed on blockchain' if status == 'failed' else False
                        })
                except Exception as e:
                    _logger.error(f"Failed to update transaction {transaction.transaction_hash}: {str(e)}")

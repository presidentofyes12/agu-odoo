from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from web3 import Web3
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class Web3Wallet(models.Model):
    _name = 'web3.wallet'
    _description = 'Web3 Wallet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Wallet Name', required=True, tracking=True)
    address = fields.Char(string='Wallet Address', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Owner', required=True, 
                             default=lambda self: self.env.user)
    network_id = fields.Many2one('web3.network', string='Network', required=True)
    balance = fields.Float(string='Balance', digits=(18,8), tracking=True)
    last_sync = fields.Datetime(string='Last Sync')
    state = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected')
    ], string='Status', default='disconnected', tracking=True)
    currency_symbol = fields.Char(related='network_id.currency_symbol', string='Currency')
    transaction_ids = fields.One2many('web3.transaction', 'wallet_id', string='Transactions')
    transaction_count = fields.Integer(compute='_compute_transaction_count', string='Transaction Count')

    _sql_constraints = [
        ('unique_address_per_user', 'unique(user_id,address,network_id)', 
         'This wallet address is already registered for this user on this network!')
    ]

    @api.constrains('address')
    def _check_address(self):
        for wallet in self:
            if not Web3.is_address(wallet.address):
                raise ValidationError(_('Invalid Ethereum address format'))

    @api.depends('transaction_ids')
    def _compute_transaction_count(self):
        for wallet in self:
            wallet.transaction_count = len(wallet.transaction_ids)

    def action_connect_wallet(self):
        """Connect the wallet"""
        self.ensure_one()
        self.state = 'connected'
        self.last_sync = fields.Datetime.now()
        self._sync_balance()
        return True

    def action_disconnect_wallet(self):
        """Disconnect the wallet"""
        self.ensure_one()
        self.state = 'disconnected'
        return True

    def action_send_transaction(self):
        """Open the send transaction wizard"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please connect your wallet first."))
        
        return {
            'name': _('Send Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'send.transaction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wallet_id': self.id,
                'default_from_address': self.address,
                'default_network_id': self.network_id.id,
            }
        }

    def _sync_balance(self):
        """Update wallet balance from blockchain"""
        self.ensure_one()
        try:
            web3 = self.network_id.get_web3()
            balance_wei = web3.eth.get_balance(self.address)
            self.balance = float(web3.from_wei(balance_wei, 'ether'))
            _logger.info(f"Updated balance for wallet {self.address}: {self.balance} {self.currency_symbol}")
        except Exception as e:
            _logger.error(f"Failed to sync balance for wallet {self.address}: {str(e)}")
            raise UserError(_("Failed to sync wallet balance: %s") % str(e))

    def _sync_transactions(self):
        """Sync recent transactions from blockchain"""
        self.ensure_one()
        try:
            web3 = self.network_id.get_web3()
            latest_block = web3.eth.block_number
            from_block = latest_block - 1000  # Last 1000 blocks

            for block_number in range(from_block, latest_block + 1):
                block = web3.eth.get_block(block_number, full_transactions=True)
                for tx in block.transactions:
                    if tx['from'].lower() == self.address.lower() or \
                       (tx['to'] and tx['to'].lower() == self.address.lower()):
                        self._create_transaction_from_data(tx, block.timestamp)

            _logger.info(f"Synced transactions for wallet {self.address}")
        except Exception as e:
            _logger.error(f"Failed to sync transactions for wallet {self.address}: {str(e)}")
            raise UserError(_("Failed to sync transactions: %s") % str(e))

    def _create_transaction_from_data(self, tx_data, timestamp):
        """Create transaction record from blockchain data"""
        tx_hash = tx_data['hash'].hex()
        existing_tx = self.env['web3.transaction'].search([
            ('tx_hash', '=', tx_hash),
            ('wallet_id', '=', self.id)
        ])

        if not existing_tx:
            self.env['web3.transaction'].create({
                'wallet_id': self.id,
                'tx_hash': tx_hash,
                'from_address': tx_data['from'],
                'to_address': tx_data['to'],
                'value': float(Web3.from_wei(tx_data['value'], 'ether')),
                'gas_price': float(Web3.from_wei(tx_data['gasPrice'], 'gwei')),
                'gas_used': tx_data['gas'],
                'timestamp': datetime.fromtimestamp(timestamp),
                'network_id': self.network_id.id,
                'status': 'confirmed'
            })

    @api.model
    def cron_sync_wallets(self):
        """Cron job to sync connected wallets"""
        wallets = self.search([('state', '=', 'connected')])
        for wallet in wallets:
            try:
                wallet.action_sync()
            except Exception as e:
                _logger.error(f"Failed to sync wallet {wallet.address}: {str(e)}")

odoo.define('web3_wallet.transaction_history', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;

    var TransactionHistory = Widget.extend({
        template: 'web3_wallet.TransactionHistory',
        events: {
            'click .o_view_transaction': '_onViewTransaction'
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.wallet = options.wallet;
            this.transactions = [];
            this.currentNetwork = options.currentNetwork;
        },

        willStart: function() {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadTransactions()
            ]);
        },

        _loadTransactions: function() {
            if (!this.wallet?.id) return Promise.resolve();

            return this._rpc({
                route: '/web3_wallet/get_transactions',
                params: {
                    wallet_id: this.wallet.id,
                    limit: 20
                }
            }).then(result => {
                if (result.success) {
                    this.transactions = result.transactions;
                    this._render();
                }
            });
        },

        _render: function() {
            this.$('.o_history_tbody').empty();
            
            this.transactions.forEach(tx => {
                const isSent = tx.from_address.toLowerCase() === this.wallet.address.toLowerCase();
                const $row = $('<tr>').append(
                    $('<td>').text(isSent ? _t('Sent') : _t('Received')),
                    $('<td>').text(`${tx.value} ${this.wallet.currency_symbol || 'ETH'}`),
                    $('<td>').text(isSent ? tx.to_address : tx.from_address),
                    $('<td>').append(
                        $('<span>')
                            .addClass(`o_tx_status ${tx.status}`)
                            .text(this._formatStatus(tx.status))
                    ),
                    $('<td>').append(
                        $('<button>')
                            .addClass('btn btn-link o_view_transaction')
                            .attr('data-hash', tx.hash)
                            .append($('<i>').addClass('fa fa-external-link'))
                    )
                );
                this.$('.o_history_tbody').append($row);
            });
        },

        _formatStatus: function(status) {
            return {
                'pending': _t('Pending'),
                'confirmed': _t('Confirmed'),
                'failed': _t('Failed')
            }[status] || status;
        },

        _onViewTransaction: function(ev) {
            const txHash = $(ev.currentTarget).data('hash');
            if (txHash && this.currentNetwork?.explorer_url) {
                window.open(`${this.currentNetwork.explorer_url}/tx/${txHash}`, '_blank');
            }
        },

        refresh: function() {
            return this._loadTransactions();
        }
    });

    return TransactionHistory;
});

odoo.define('web3_wallet.transaction_form', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;

    var TransactionForm = Widget.extend({
        template: 'web3_wallet.TransactionForm',
        events: {
            'input .o_to_address': '_onInputChange',
            'input .o_amount': '_onInputChange',
            'click .o_send_tx': '_onSendTransaction'
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.wallet = options.wallet;
            this.web3 = options.web3;
        },

        _onInputChange: function() {
            this._updateGasEstimate();
        },

        _updateGasEstimate: async function() {
            const toAddress = this.$('.o_to_address').val();
            const amount = this.$('.o_amount').val();

            if (this.web3.utils.isAddress(toAddress) && amount > 0) {
                try {
                    const result = await this._rpc({
                        route: '/web3_wallet/estimate_gas',
                        params: {
                            to_address: toAddress,
                            amount: amount,
                            wallet_id: this.wallet.id
                        }
                    });

                    if (result.success) {
                        this.$('.o_gas_estimate').text(result.gas_estimate);
                        this.$('.o_total_cost').text(
                            `${parseFloat(amount) + parseFloat(result.total_gas_cost)} ${this.wallet.currency_symbol || 'ETH'}`
                        );
                    }
                } catch (error) {
                    console.error('Error estimating gas:', error);
                }
            }
        },

        _onSendTransaction: async function() {
            const toAddress = this.$('.o_to_address').val();
            const amount = this.$('.o_amount').val();

            if (!this.web3.utils.isAddress(toAddress)) {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Invalid recipient address')
                });
                return;
            }

            if (!amount || parseFloat(amount) <= 0) {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Invalid amount')
                });
                return;
            }

            this.trigger_up('send_transaction', {
                to_address: toAddress,
                amount: amount
            });
        },

        clear: function() {
            this.$('.o_to_address').val('');
            this.$('.o_amount').val('');
            this.$('.o_gas_estimate').text('0');
            this.$('.o_total_cost').text('0');
        }
    });

    return TransactionForm;
});

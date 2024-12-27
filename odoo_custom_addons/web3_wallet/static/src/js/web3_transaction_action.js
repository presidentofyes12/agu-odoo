odoo.define('web3_wallet.transaction_action', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var _t = core._t;

    var Web3TransactionAction = AbstractAction.extend({
        init: function(parent, action) {
            this._super.apply(this, arguments);
            this.actionParams = action.params || {};
        },

        start: async function() {
            await this._super.apply(this, arguments);
            return this._handleTransaction();
        },

        async _handleTransaction() {
            try {
                if (!window.ethereum) {
                    throw new Error(_t("MetaMask not found"));
                }

                // Ensure we're on the correct network
                const chainId = await window.ethereum.request({ method: 'eth_chainId' });
                if (parseInt(chainId, 16) !== this.actionParams.chain_id) {
                    throw new Error(_t("Please switch to the correct network in MetaMask"));
                }

                // Get current account
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                const from = accounts[0];

                // Prepare transaction
                const transactionParameters = {
                    from: from,
                    to: this.actionParams.to_address,
                    value: '0x' + (this.actionParams.value * 1e18).toString(16), // Convert ETH to Wei and then to hex
                };

                // Send transaction through MetaMask
                const txHash = await window.ethereum.request({
                    method: 'eth_sendTransaction',
                    params: [transactionParameters],
                });

                // Update transaction record with hash
                await rpc.query({
                    model: 'web3.transaction',
                    method: 'write',
                    args: [[this.actionParams.transaction_id], {
                        tx_hash: txHash,
                    }],
                });

                // Show success message using the notification service
                this.displayNotification({
                    title: _t('Success'),
                    message: _t('Transaction sent: ') + txHash,
                    type: 'success',
                });

                // Return to previous view
                this.do_action({
                    type: 'ir.actions.act_window_close'
                });

            } catch (error) {
                console.error('Transaction error:', error);
                
                // Show error message using the notification service
                this.displayNotification({
                    title: _t('Error'),
                    message: error.message || _t('Transaction failed'),
                    type: 'danger',
                    sticky: true
                });

                // Clean up failed transaction
                await rpc.query({
                    model: 'web3.transaction',
                    method: 'unlink',
                    args: [[this.actionParams.transaction_id]],
                });

                // Return to previous view
                this.do_action({
                    type: 'ir.actions.act_window_close'
                });
            }
        },
    });

    core.action_registry.add('web3_send_transaction', Web3TransactionAction);

    return Web3TransactionAction;
});

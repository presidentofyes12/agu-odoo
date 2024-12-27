odoo.define('web3_wallet.wallet_display', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;

    var WalletDisplay = Widget.extend({
        template: 'web3_wallet.WalletDisplay',
        events: {
            'click .o_view_explorer': '_onViewExplorer',
            'change .o_network_selector': '_onNetworkChange'
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.wallet = options.wallet || {};
            this.networks = options.networks || [];
        },

        willStart: function() {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadNetworkData()
            ]);
        },

        _loadNetworkData: function() {
            return this._rpc({
                route: '/web3_wallet/get_networks',
                params: {}
            }).then(result => {
                this.networks = result.networks || [];
            });
        },

        _onViewExplorer: function() {
            if (this.wallet.address && this.wallet.network_id) {
                const network = this.networks.find(n => n.id === this.wallet.network_id);
                if (network && network.explorer_url) {
                    window.open(`${network.explorer_url}/address/${this.wallet.address}`, '_blank');
                }
            }
        },

        _onNetworkChange: function(ev) {
            const chainId = parseInt($(ev.currentTarget).val());
            this.trigger_up('network_changed', { chainId: chainId });
        },

        updateDisplay: function(walletData) {
            this.wallet = walletData;
            this._updateUI();
        },

        _updateUI: function() {
            this.$('.o_wallet_address').val(this.wallet.address || '');
            this.$('.o_wallet_balance').text(
                this.wallet.balance ? 
                `${this.wallet.balance} ${this.wallet.currency_symbol || 'ETH'}` : 
                '0 ETH'
            );
            this.$('.o_network_selector').val(this.wallet.network_id);
        }
    });

    return WalletDisplay;
});

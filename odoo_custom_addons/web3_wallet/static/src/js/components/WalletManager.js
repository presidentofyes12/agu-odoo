odoo.define('web3_wallet.wallet_manager_component', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var WalletDisplay = require('web3_wallet.wallet_display');
    var TransactionForm = require('web3_wallet.transaction_form');
    var TransactionHistory = require('web3_wallet.transaction_history');
    var _t = core._t;

    var WalletManagerComponent = Widget.extend({
        template: 'web3_wallet.WalletManager',
        custom_events: {
            'network_changed': '_onNetworkChanged',
            'send_transaction': '_onSendTransaction'
        },

        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.wallet = null;
            this.web3 = null;
            this.currentAccount = null;
            this.currentNetwork = null;
            this.childWidgets = {
                walletDisplay: null,
                transactionForm: null,
                transactionHistory: null
            };
        },

        willStart: function () {
            return Promise.all([
                this._super.apply(this, arguments),
                this._initializeWeb3()
            ]);
        },

        start: async function () {
            await this._super.apply(this, arguments);
            this._initializeComponents();
            this._setupEventListeners();
            return this;
        },

        _initializeWeb3: async function () {
            if (typeof window.ethereum !== 'undefined') {
                this.web3 = new Web3(window.ethereum);
                // Check if already connected
                try {
                    const accounts = await window.ethereum.request({
                        method: 'eth_accounts'
                    });
                    if (accounts.length > 0) {
                        await this._handleAccountConnect(accounts[0]);
                    }
                } catch (error) {
                    console.error('Error checking accounts:', error);
                }
            } else {
                this.displayNotification({
                    type: 'warning',
                    title: _t('Web3 Not Found'),
                    message: _t('Please install MetaMask or another Web3 wallet.')
                });
            }
        },

        _initializeComponents: function () {
            // Initialize Wallet Display
            this.childWidgets.walletDisplay = new WalletDisplay(this, {
                wallet: this.wallet
            });
            this.childWidgets.walletDisplay.appendTo(this.$('.o_wallet_display_container'));

            // Initialize Transaction Form
            this.childWidgets.transactionForm = new TransactionForm(this, {
                wallet: this.wallet,
                web3: this.web3
            });
            this.childWidgets.transactionForm.appendTo(this.$('.o_transaction_form_container'));

            // Initialize Transaction History
            this.childWidgets.transactionHistory = new TransactionHistory(this, {
                wallet: this.wallet,
                currentNetwork: this.currentNetwork
            });
            this.childWidgets.transactionHistory.appendTo(this.$('.o_transaction_history_container'));

            // Set initial visibility
            this._updateComponentVisibility();
        },

        _setupEventListeners: function () {
            if (window.ethereum) {
                window.ethereum.on('accountsChanged', accounts => {
                    if (accounts.length === 0) {
                        this._handleDisconnect();
                    } else {
                        this._handleAccountConnect(accounts[0]);
                    }
                });

                window.ethereum.on('chainChanged', chainId => {
                    this._handleNetworkChange(chainId);
                });

                window.ethereum.on('connect', connectInfo => {
                    this._handleConnect(connectInfo);
                });

                window.ethereum.on('disconnect', error => {
                    this._handleDisconnect();
                });
            }
        },

        _handleAccountConnect: async function (account) {
            try {
                const chainId = await window.ethereum.request({
                    method: 'eth_chainId'
                });

                const result = await this._rpc({
                    route: '/web3_wallet/connect',
                    params: {
                        address: account,
                        chain_id: parseInt(chainId, 16)
                    }
                });

                if (result.success) {
                    this.wallet = result.wallet;
                    this.currentAccount = account;
                    this.currentNetwork = result.network;
                    this._updateComponents();
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Connection Error'),
                    message: error.message
                });
            }
        },

        _handleDisconnect: async function () {
            if (this.wallet?.id) {
                await this._rpc({
                    route: '/web3_wallet/disconnect',
                    params: {
                        wallet_id: this.wallet.id
                    }
                });
            }

            this.wallet = null;
            this.currentAccount = null;
            this.currentNetwork = null;
            this._updateComponents();
        },

        _handleNetworkChange: async function (chainId) {
            const networkId = parseInt(chainId, 16);
            try {
                const result = await this._rpc({
                    route: '/web3_wallet/get_networks',
                    params: { chain_id: networkId }
                });

                if (result.success) {
                    this.currentNetwork = result.network;
                    await this._updateComponents();
                }
            } catch (error) {
                console.error('Error handling network change:', error);
            }
        },

        _handleConnect: function (connectInfo) {
            this.displayNotification({
                type: 'success',
                title: _t('Connected'),
                message: _t('Successfully connected to Web3 wallet.')
            });
        },

        _updateComponents: function () {
            if (this.wallet) {
                // Update wallet display
                this.childWidgets.walletDisplay.updateDisplay({
                    ...this.wallet,
                    currentNetwork: this.currentNetwork
                });

                // Reset and update transaction form
                this.childWidgets.transactionForm.clear();

                // Refresh transaction history
                this.childWidgets.transactionHistory.refresh();
            }

            this._updateComponentVisibility();
        },

        _updateComponentVisibility: function () {
            const isConnected = Boolean(this.wallet);
            this.$('.o_transaction_form_container').toggleClass('d-none', !isConnected);
            this.$('.o_transaction_history_container').toggleClass('d-none', !isConnected);
            this.$('.o_connect_wallet').toggleClass('d-none', isConnected);
            this.$('.o_disconnect_wallet').toggleClass('d-none', !isConnected);
        },

        _onNetworkChanged: async function (ev) {
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: `0x${ev.data.chainId.toString(16)}` }],
                });
            } catch (error) {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Network Switch Failed'),
                    message: error.message
                });
            }
        },

        _onSendTransaction: async function (ev) {
            const { to_address, amount } = ev.data;
            try {
                const tx = {
                    from: this.currentAccount,
                    to: to_address,
                    value: this.web3.utils.toWei(amount.toString(), 'ether')
                };

                const gasEstimate = await this.web3.eth.estimateGas(tx);
                tx.gas = gasEstimate;

                const txHash = await window.ethereum.request({
                    method: 'eth_sendTransaction',
                    params: [tx],
                });

                this.displayNotification({
                    type: 'success',
                    title: _t('Transaction Sent'),
                    message: _t('Transaction hash: ') + txHash
                });

                // Clear the form and refresh history
                this.childWidgets.transactionForm.clear();
                await this.childWidgets.transactionHistory.refresh();

            } catch (error) {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Transaction Failed'),
                    message: error.message
                });
            }
        },

        destroy: function () {
            // Clean up event listeners
            if (window.ethereum) {
                window.ethereum.removeAllListeners();
            }
            // Destroy child widgets
            Object.values(this.childWidgets).forEach(widget => {
                if (widget && widget.destroy) {
                    widget.destroy();
                }
            });
            this._super.apply(this, arguments);
        }
    });

    return WalletManagerComponent;
});

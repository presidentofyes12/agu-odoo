odoo.define('web3_wallet.wallet_manager', function (require) {
    'use strict';

    var core = require('web.core');
    var Widget = require('web.Widget');
    var Dialog = require('web.Dialog');
    var QWeb = core.qweb;
    var _t = core._t;

    // Register client action for sending transactions
    core.action_registry.add('web3_send_transaction', function(parent, action) {
        return handleMetaMaskTransaction(action.params);
    });

    async function handleMetaMaskTransaction(params) {
        try {
            if (!window.ethereum) {
                throw new Error(_t("MetaMask not found"));
            }

            // Ensure we're on the correct network
            const chainId = await window.ethereum.request({ method: 'eth_chainId' });
            if (parseInt(chainId, 16) !== params.chain_id) {
                throw new Error(_t("Please switch to the correct network in MetaMask"));
            }

            // Get current account
            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            const from = accounts[0];

            // Prepare transaction
            const transactionParameters = {
                from: from,
                to: params.to_address,
                value: '0x' + (params.value * 1e18).toString(16), // Convert ETH to Wei and then to hex
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
                args: [params.transaction_id, {
                    tx_hash: txHash,
                }],
            });

            // Show success message
            core.bus.trigger('display-notification', {
                title: _t('Success'),
                message: _t('Transaction sent: ') + txHash,
                type: 'success',
            });

            return true;
        } catch (error) {
            console.error('Transaction error:', error);
            
            // Show error message
            core.bus.trigger('display-notification', {
                title: _t('Error'),
                message: error.message || _t('Transaction failed'),
                type: 'danger',
            });

            // Clean up failed transaction
            await rpc.query({
                model: 'web3.transaction',
                method: 'unlink',
                args: [params.transaction_id],
            });

            return false;
        }
    }

    var WalletManager = Widget.extend({
        template: 'wallet_management',
        events: {
            'click .o_connect_wallet': '_onConnectWallet',
            'click .o_disconnect_wallet': '_onDisconnectWallet',
            'click .o_send_tx': '_onSendTransaction',
            'change .o_network_selector': '_onNetworkChange',
            'input .o_to_address, .o_amount': '_onTransactionInputChange',
            'click .o_view_explorer': '_onViewExplorer'
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.web3 = null;
            this.currentAccount = null;
            this.currentNetwork = null;
            this.networks = [];
            this.transactions = [];
        },

        start: async function() {
            await this._super.apply(this, arguments);
            await this._initializeWeb3();
            await this._loadNetworks();
            this._startListeners();
            return this;
        },

        // Web3 Initialization
        _initializeWeb3: async function() {
            if (typeof window.ethereum !== 'undefined') {
                this.web3 = new Web3(window.ethereum);
                this.isMetaMaskInstalled = true;
            } else {
                this._showError(_t("Please install MetaMask or another Web3 wallet."));
                this.isMetaMaskInstalled = false;
            }
        },

        // Load Available Networks
        _loadNetworks: async function() {
            try {
                const result = await this._rpc({
                    route: '/web3_wallet/get_networks',
                    params: {}
                });
                
                if (result.networks) {
                    this.networks = result.networks;
                    this._updateNetworkSelector();
                }
            } catch (error) {
                this._showError(_t("Failed to load networks"));
            }
        },

        // Event Listeners
        _startListeners: function() {
            if (window.ethereum) {
                window.ethereum.on('accountsChanged', (accounts) => {
                    if (accounts.length === 0) {
                        this._handleDisconnect();
                    } else {
                        this._handleAccountChange(accounts[0]);
                    }
                });

                window.ethereum.on('chainChanged', (chainId) => {
                    this._handleNetworkChange(chainId);
                });
            }
        },

        // Connect Wallet
        _onConnectWallet: async function() {
            try {
                if (!this.web3) {
                    throw new Error(_t("Web3 not initialized"));
                }

                const accounts = await window.ethereum.request({
                    method: 'eth_requestAccounts'
                });

                if (accounts.length === 0) {
                    throw new Error(_t("No accounts found"));
                }

                const chainId = await window.ethereum.request({
                    method: 'eth_chainId'
                });

                // Register wallet in backend
                const result = await this._rpc({
                    route: '/web3_wallet/connect',
                    params: {
                        address: accounts[0],
                        chain_id: parseInt(chainId, 16)
                    }
                });

                if (result.success) {
                    this.currentAccount = accounts[0];
                    this.currentNetwork = this.networks.find(n => n.chain_id === parseInt(chainId, 16));
                    this._updateUI();
                    this._loadTransactionHistory();
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                this._showError(error.message);
            }
        },

        // Disconnect Wallet
        _onDisconnectWallet: async function() {
            try {
                if (this.currentAccount) {
                    await this._rpc({
                        route: '/web3_wallet/disconnect',
                        params: {
                            address: this.currentAccount
                        }
                    });
                }
                this._handleDisconnect();
            } catch (error) {
                this._showError(error.message);
            }
        },

        // Send Transaction
        _onSendTransaction: async function() {
            try {
                const toAddress = this.$('.o_to_address').val();
                const amount = this.$('.o_amount').val();

                if (!Web3.utils.isAddress(toAddress)) {
                    throw new Error(_t("Invalid address"));
                }

                if (!amount || parseFloat(amount) <= 0) {
                    throw new Error(_t("Invalid amount"));
                }

                const tx = {
                    from: this.currentAccount,
                    to: toAddress,
                    value: Web3.utils.toWei(amount.toString(), 'ether'),
                    gas: 21000, // Standard gas limit for ETH transfers
                };

                // Send transaction
                const txHash = await window.ethereum.request({
                    method: 'eth_sendTransaction',
                    params: [tx],
                });

                this._showSuccess(_t("Transaction sent: ") + txHash);
                this._loadTransactionHistory();
            } catch (error) {
                this._showError(error.message);
            }
        },

        // Network Change Handler
        _onNetworkChange: async function(ev) {
            const chainId = parseInt($(ev.currentTarget).val());
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: '0x' + chainId.toString(16) }],
                });
            } catch (error) {
                this._showError(error.message);
            }
        },

        // UI Updates
        _updateUI: function() {
            if (this.currentAccount) {
                this.$('.o_wallet_address').val(this.currentAccount);
                this.$('.o_connect_wallet').addClass('d-none');
                this.$('.o_disconnect_wallet').removeClass('d-none');
                this._updateBalance();
            } else {
                this.$('.o_wallet_address').val('');
                this.$('.o_connect_wallet').removeClass('d-none');
                this.$('.o_disconnect_wallet').addClass('d-none');
                this.$('.o_wallet_balance').text('0');
            }
        },

        _updateBalance: async function() {
            if (this.currentAccount && this.web3) {
                try {
                    const balance = await this.web3.eth.getBalance(this.currentAccount);
                    const balanceEth = Web3.utils.fromWei(balance, 'ether');
                    this.$('.o_wallet_balance').text(
                        `${parseFloat(balanceEth).toFixed(4)} ${this.currentNetwork?.currency_symbol || 'ETH'}`
                    );
                } catch (error) {
                    console.error('Error fetching balance:', error);
                }
            }
        },

        _updateNetworkSelector: function() {
            const $selector = this.$('.o_network_selector');
            $selector.empty();
            this.networks.forEach(network => {
                $selector.append(new Option(network.name, network.chain_id));
            });
        },

        // Transaction History
        _loadTransactionHistory: async function() {
            if (!this.currentAccount) return;

            try {
                const result = await this._rpc({
                    route: '/web3_wallet/get_transactions',
                    params: {
                        address: this.currentAccount
                    }
                });

                if (result.transactions) {
                    this._renderTransactionHistory(result.transactions);
                }
            } catch (error) {
                console.error('Error loading transactions:', error);
            }
        },

        _renderTransactionHistory: function(transactions) {
            const $tbody = this.$('.o_history_tbody');
            $tbody.empty();

            transactions.forEach(tx => {
                const isSent = tx.from_address.toLowerCase() === this.currentAccount.toLowerCase();
                const $row = $('<tr>').append(
                    $('<td>').text(isSent ? _t('Sent') : _t('Received')),
                    $('<td>').text(`${tx.value} ${this.currentNetwork?.currency_symbol || 'ETH'}`),
                    $('<td>').text(isSent ? tx.to_address : tx.from_address),
                    $('<td>').append(
                        $('<span>')
                            .addClass(`o_tx_status ${tx.status}`)
                            .text(tx.status)
                    ),
                    $('<td>').append(
                        $('<a>')
                            .attr('href', `${this.currentNetwork?.explorer_url}/tx/${tx.hash}`)
                            .attr('target', '_blank')
                            .append($('<i>').addClass('fa fa-external-link'))
                    )
                );
                $tbody.append($row);
            });
        },

        // Utility Functions
        _showError: function(message) {
            this.do_warn(_t("Error"), message);
        },

        _showSuccess: function(message) {
            this.do_notify(_t("Success"), message);
        },

        _handleDisconnect: function() {
            this.currentAccount = null;
            this.currentNetwork = null;
            this._updateUI();
            this.$('.o_history_tbody').empty();
        },

        _handleAccountChange: function(account) {
            this.currentAccount = account;
            this._updateUI();
            this._loadTransactionHistory();
        },

        _handleNetworkChange: async function(chainId) {
            const networkId = parseInt(chainId, 16);
            this.currentNetwork = this.networks.find(n => n.chain_id === networkId);
            this.$('.o_network_selector').val(networkId);
            await this._updateBalance();
            this._loadTransactionHistory();
        },

        destroy: function() {
            if (window.ethereum) {
                window.ethereum.removeAllListeners();
            }
            this._super.apply(this, arguments);
        }
    });

    core.action_registry.add('web3_wallet.wallet_manager', WalletManager);

    return WalletManager;
});

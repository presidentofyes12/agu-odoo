/** @odoo-module **/

import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

class WalletConnectorComponent extends Component {
    setup() {
        this.state = useState({
            isConnected: false,
            account: null,
            chainId: null,
            balance: null,
            provider: null,
            error: null
        });
        
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
        
        onMounted(() => {
            this.initializeProvider();
        });
    }

    async initializeProvider() {
        if (typeof window.ethereum !== 'undefined') {
            this.state.provider = window.ethereum;
            this.setupEventListeners();
        }
    }

    setupEventListeners() {
        if (!this.state.provider) return;

        this.state.provider.on('accountsChanged', (accounts) => {
            if (accounts.length === 0) {
                this.handleDisconnect();
            } else {
                this.state.account = accounts[0];
                this.updateBalance();
            }
        });

        this.state.provider.on('chainChanged', async (chainId) => {
            this.state.chainId = chainId;
            await this.updateBalance();
        });
    }

    async handleConnect() {
        try {
            if (!this.state.provider) {
                throw new Error('MetaMask not installed');
            }

            const accounts = await this.state.provider.request({
                method: 'eth_requestAccounts'
            });

            this.state.account = accounts[0];
            this.state.chainId = await this.state.provider.request({
                method: 'eth_chainId'
            });
            
            await this.updateBalance();
            await this.updateServerState();

            this.state.isConnected = true;

            this.notification.add({
                title: 'Success',
                message: 'Wallet connected successfully',
                type: 'success'
            });

            // Reload the view
            await this.action.doAction({
                type: 'ir.actions.client',
                tag: 'reload',
            });

        } catch (error) {
            this.notification.add({
                title: 'Error',
                message: error.message,
                type: 'danger'
            });
        }
    }

    async updateBalance() {
        if (this.state.provider && this.state.account) {
            try {
                const balance = await this.state.provider.request({
                    method: 'eth_getBalance',
                    params: [this.state.account, 'latest']
                });
                this.state.balance = parseInt(balance, 16) / 1e18;
            } catch (error) {
                console.error('Error fetching balance:', error);
            }
        }
    }

    async updateServerState() {
        try {
            await this.rpc.call('/web3_wallet_connect/update_connection', {
                account: this.state.account,
                chain_id: this.state.chainId,
                provider_type: 'web3'
            });
        } catch (error) {
            console.error('Error updating server state:', error);
        }
    }

    async handleDisconnect() {
        this.state.isConnected = false;
        this.state.account = null;
        this.state.chainId = null;
        this.state.balance = null;
        await this.updateServerState();
        
        this.notification.add({
            title: 'Success',
            message: 'Wallet disconnected',
            type: 'success'
        });
    }
}

WalletConnectorComponent.template = 'web3_wallet_connect.WalletConnector';

/*
WalletConnectorComponent.components = {};

// Register the client action
const walletConnectorAction = {
    type: 'ir.actions.client',
    tag: 'wallet_connector',
    target: 'current',
    Component: WalletConnectorComponent,
};
*/

// Properly register the component
registry.category("actions").add("web3_wallet_connect.connect", {
    component: WalletConnectorComponent,
    target: 'new',
});

export default WalletConnectorComponent;
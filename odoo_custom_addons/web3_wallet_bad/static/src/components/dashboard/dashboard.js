/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class WalletDashboard extends Component {
    setup() {
        this.state = useState({
            data: {},
            loading: true
        });
        this.orm = useService("orm");
        this.action = useService("action");
        
        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                'res.users',
                'get_wallet_dashboard_data',
                []
            );
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.state.data = {};
        } finally {
            this.state.loading = false;
        }
    }

    async onCreateWallet() {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'wallet.create.wizard',
            views: [[false, 'form']],
            target: 'new',
        });
    }

    async onImportWallet() {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'wallet.import.wizard',
            views: [[false, 'form']],
            target: 'new',
        });
    }

    async onViewTransactions() {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'wallet.transaction',
            views: [[false, 'list'], [false, 'form']],
            domain: [],
        });
    }

    async onRefreshBalance() {
        await this.loadDashboardData();
    }
}

WalletDashboard.template = "web3_wallet.WalletDashboard";

// Register the client action
registry.category("client_actions").add("wallet_dashboard", {
    Component: WalletDashboard,
    props: {}  // Initialize with empty props
});

export default WalletDashboard;

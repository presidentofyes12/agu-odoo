{
    'name': 'Web3 Wallet Manager',
    'version': '1.0',
    'category': 'Cryptocurrency',
    'summary': 'Manage Web3 wallets and transactions within Odoo',
    'description': """
        Web3 Wallet Management System for Odoo
        =====================================
        * Connect to Web3 wallets (MetaMask, Rabby)
        * Send transactions
        * View transaction history
        * Support for multiple networks (Ethereum, PulseChain, Polygon)
        * Track balances and transactions
    """,
    'author': 'Your Company',
    'website': 'https://www.example.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/web3_wallet_security.xml',
        'security/ir.model.access.csv',
        'views/web3_wallet_views.xml',
        'views/menu_items.xml',
        'data/web3_network_data.xml',
        'wizards/send_transaction_wizard_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'web3_wallet/static/src/js/web3_wallet.js',
            'web3_wallet/static/src/js/web3_transaction_action.js',  # Add this line
            'web3_wallet/static/src/css/web3_wallet.css',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['web3', 'eth_account'],
    },
}

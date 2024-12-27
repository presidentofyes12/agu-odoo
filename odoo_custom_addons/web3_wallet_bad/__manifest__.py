{
    'name': 'Do Not Use - Web3 Wallet',
    'version': '1.0',
    'category': 'Blockchain',
    'summary': 'Ethereum Wallet Management System',
    'description': """
        Ethereum Wallet Management System for Odoo
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/wallet_security.xml',
        'security/ir.model.access.csv',
        'data/wallet_data.xml',
        'data/scheduled_tasks.xml',
        'views/wallet_actions.xml',  # Keep this before menus
        'views/wallet_config_views.xml',
        'views/wallet_transaction_views.xml',
        'views/res_users_views.xml',
        'views/web3_wallet_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Load OWL Components
            'web3_wallet/static/src/components/**/*.js',
            'web3_wallet/static/src/components/**/*.scss',
            'web3_wallet/static/src/components/**/*.xml',
            # Additional JS
            'web3_wallet/static/src/js/*.js',
        ],
    },
    'external_dependencies': {
        'python': ['web3', 'eth_account', 'eth_keys', 'cryptography'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

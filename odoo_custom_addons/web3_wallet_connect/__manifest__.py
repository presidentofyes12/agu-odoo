{
    'name': 'Web3 Wallet Connect',
    'version': '1.0',
    'category': 'Blockchain',
    'summary': 'Multi-protocol wallet connection management',
    'description': """
        Manage Web3 and Nostr wallet connections within Odoo
        - Support for multiple wallet providers (MetaMask, WalletConnect, etc.)
        - Nostr protocol support
        - Network management
        - Transaction handling
        - Secure key management
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/wallet_security.xml',
        'security/ir.model.access.csv',
        'views/actions.xml',
        'views/menu_views.xml',
        'views/wallet_config_views.xml',
        'views/wallet_connection_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'data/wallet_sequence.xml',
        'data/scheduled_tasks.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # CSS
            '/web3_wallet_connect/static/src/css/**/*',
            # XML Templates
            '/web3_wallet_connect/static/src/xml/**/*',
            # JavaScript
            '/web3_wallet_connect/static/src/js/**/*',
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

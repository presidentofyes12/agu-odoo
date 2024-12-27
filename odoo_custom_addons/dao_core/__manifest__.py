{
    'name': 'DAO Core',
    'version': '1.0',
    'category': 'Blockchain',
    'summary': 'Core functionality for DAO operations',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/dao_security.xml',
        'security/ir.model.access.csv',
        'data/dao_sequence.xml',
        'views/dao_config_views.xml',
        'views/dao_member_views.xml',
        'views/res_config_settings_views.xml',  # Make sure this is after models are loaded
        'data/scheduled_tasks.xml',
    ],
    'external_dependencies': {
        'python': ['web3', 'eth_account', 'eth_keys'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

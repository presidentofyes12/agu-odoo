{
    'name': 'Opinion Reputation System and Relationship Management',
    'version': '1.0',
    'category': 'Social',
    'summary': 'Prevent scams in a decentralized environment and manage family relationships',
    'author': 'Your Name',
    'website': 'https://www.example.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/user_views.xml',
        'views/question_views.xml',
        'views/prediction_views.xml',
        'views/relationship_views.xml',
        'views/relative_views.xml',
        'data/default_relationships.xml',
        'wizards/load_questions_wizard_view.xml',
        'wizards/update_relative_wizard_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# -*- coding: utf-8 -*-
{
    'name': "Wedding Plan",

    'summary': """
        Wedding Plan Management.""",

    'description': """
        Wedding Plan Management.
    """,

    'author': "Farhan Sabili",
    'website': "https://www.linkedin.com/in/billylvn/",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'mail', 'website'],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizards/views.xml',
        # 'views/assets.xml',
        'views/templates.xml',
        'views/wedding_calendar.xml',
        'views/wedding_budget.xml',
        'views/wedding_invitation.xml',
        'views/wedding_expenses.xml',
        'views/wedding_session.xml',
        'views/wedding_wishes.xml',
        'views/menu_items.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            '/wedding_plan/static/src/js/wedding.js',
            '/wedding_plan/static/src/css/wedding.css',
            'https://cdn.jsdelivr.net/npm/lazyload@2.0.0-rc.2/lazyload.js',
            # 'https://cdn.jsdelivr.net/npm/sweetalert2@11',
            'https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.all.min.js',
            'https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Roboto:wght@100&display=swap',
        ],
    },

    'application': True
}

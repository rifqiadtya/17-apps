# -*- coding: utf-8 -*-
{
    'name': 'Split Bill',
    'version': '1.0',
    'summary': 'Advanced bill splitting functionality',
    'description': """
        Split Bill Module
        ================
        This module provides advanced bill splitting functionality including:
        * Complex splitting dynamics
        * Delivery fee distribution
        * Discount allocation
        * Multiple splitting methods
        * Split history tracking
    """,
    'category': 'Accounting/Split Bill',
    'author': 'Odoo',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'sale',
        'point_of_sale',
    ],
    'data': [
        'security/split_bill_security.xml',
        'security/ir.model.access.csv',
        'views/split_bill_views.xml',
        'views/split_bill_session_views.xml',
        'views/split_bill_participant_views.xml',
        'views/split_bill_item_views.xml',
        'views/split_bill_menus.xml',
        'wizards/split_bill_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'split_bill/static/src/js/**/*',
            'split_bill/static/src/xml/**/*',
            'split_bill/static/src/scss/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
}

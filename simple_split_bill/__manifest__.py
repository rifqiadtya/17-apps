# -*- coding: utf-8 -*-
{
    'name': 'Simple Split Bill',
    'version': '1.0',
    'summary': 'Simple bill splitting for food delivery services',
    'description': """
        Simple Split Bill Module
        =======================
        A simplified bill splitting solution for food delivery services like Grab, GoFood, and ShopeeFood.
        Track and split food delivery expenses easily among participants.
    """,
    'category': 'Accounting/Split Bill',
    'author': 'Odoo',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'web',
        'website',
    ],
    'data': [
        'security/simple_split_bill_security.xml',
        'security/ir.model.access.csv',
        'views/food_order_views.xml',
        'views/food_order_line_views.xml',
        'views/food_order_payment_views.xml',
        'views/simple_split_bill_menus.xml',
        'views/templates/food_receipt_template.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}

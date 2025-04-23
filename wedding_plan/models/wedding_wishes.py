from odoo import _, api, fields, models

class WeddingWishes(models.Model):
    _name = 'wedding.wishes'
    _description = 'Wedding Wishes'
    _order = 'create_date desc'
    
    name = fields.Many2one('res.partner', string='Name')
    wish = fields.Text('Wish')
    attend = fields.Selection([
        ('yes', 'Yes, I will gladly attend'),
        ('no', 'No, regretfully I won’t be able to attend'),
    ], string='Attend')
    quantity = fields.Integer('Quantity')
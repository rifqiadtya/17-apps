from odoo import _, api, fields, models

class WeddingSession(models.Model):
    _name = 'wedding.session'
    _description = 'Wedding Session'
    
    name = fields.Char('Name')
    time = fields.Char('Time')
from odoo import _, api, fields, models

class WeddingCalendar(models.Model):
    _name = 'wedding.calendar'
    _description = 'Wedding Schedule'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    name = fields.Char(tracking=True)
    start_date = fields.Datetime('Start Date', tracking=True)
    end_date = fields.Datetime('End Date', tracking=True)
    description = fields.Text(tracking=True)
    partner_ids = fields.Many2many('res.partner', string='Attendees', tracking=True)
    planning_line_id = fields.Many2one('wedding.budget.planing.line', string='Planning Line', ondelete='cascade')
from odoo import _, api, fields, models

class WeddingExpenses(models.Model):
    _name = 'wedding.expenses'
    _description = 'Wedding Expenses'
    
    name = fields.Char(required=True)
    line_ids = fields.One2many('wedding.expenses.line', 'wedding_expenses_id', string='Line')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id)
    grand_total = fields.Monetary(compute='_compute_grand_total', string='Grand Total')
    
    @api.depends('line_ids')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = sum(rec.line_ids.mapped('amount'))


class WeddingExpensesLine(models.Model):
    _name = 'wedding.expenses.line'
    _description = 'Wedding Expenses Line'
    
    name = fields.Char(required=True)
    amount = fields.Monetary('')
    wedding_expenses_id = fields.Many2one('wedding.expenses', string='Wedding Expenses')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id)
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

class WeddingBudget(models.Model):
    _name = 'wedding.budget'
    _description = 'Wedding Budget'
    
    name = fields.Char('')
    amount = fields.Monetary('')
    remaining_amount = fields.Monetary('Remaining Amount', compute="get_remaining_amount")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id)
    planning_ids = fields.One2many('wedding.budget.planning', 'budget_id', string='Planning')

    def unlink(self):
        for rec in self:
            if rec.planning_ids:
                raise ValidationError(("There's planning associated with this Budget."))
            return super(WeddingBudget, self).unlink()

    def get_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - sum(rec.planning_ids.line_ids.filtered(lambda x: x.done == True).mapped('subtotal'))

class WeddingBudgetPlanning(models.Model):
    _name = 'wedding.budget.planning'
    _description = 'Wedding Budget Planning'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    name = fields.Char(readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('done', 'Done'),
    ], string='Status', default='draft', copy=False, tracking=True)
    due_date = fields.Date('Due Date', readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    budget_id = fields.Many2one('wedding.budget', string='Budget', readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    user_id = fields.Many2one('res.users', string='Responsible', readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    line_ids = fields.One2many('wedding.budget.planning.line', 'planning_id', string='Details', tracking=True)
    progress = fields.Float(compute='_compute_progress', string='Progress', readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    planning_line_id = fields.Many2one('wedding.budget.planning.line', string='Planning Line')

    @api.depends('line_ids')
    def _compute_progress(self):
        for rec in self.filtered(lambda x: x.budget_id != False):
            rec.progress = False
            if rec.line_ids:
                rec.progress = len(rec.line_ids.filtered(lambda x: x.done == True)) / len(rec.line_ids)*100

    def button_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})

    def button_submit(self):
        for rec in self:
            rec.write({'state': 'submit'})

    def button_done(self):
        for rec in self:
            if len(rec.line_ids) == len(rec.line_ids.filtered(lambda x: x.done == True)):
                rec.write({'state': 'done'})
            else:
                raise UserError("The items must be done.")

class WeddingBudgetPlanningLine(models.Model):
    _name = 'wedding.budget.planning.line'
    _description = 'Wedding Budget Planning Line'
    
    planning_id = fields.Many2one('wedding.budget.planning', string='Planning', ondelete="cascade")
    name = fields.Char('Description')
    quantity = fields.Float('')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id)
    unit_price = fields.Monetary('Unit Price')
    subtotal = fields.Monetary(compute="get_subtotal")
    done = fields.Boolean('')
    wedding_calendar_line = fields.One2many('wedding.calendar', 'planning_line_id', string='Wedding Calendar')
    wedding_budget_line = fields.One2many('wedding.budget.planning', 'planning_line_id', string='Wedding Planning')
    remark = fields.Char('Remark')

    def generate_schedule(self):
        self.ensure_one()
        return {
            'name': _('Schedule'),
            'view_mode': 'form',
            'res_model': 'wedding.calendar',
            'type': 'ir.actions.act_window',
            'context': {'default_name': self.name, 'default_planning_line_id': self.id},
            'target': 'current',
        }

    @api.depends('quantity', 'unit_price')
    def get_subtotal(self):
        for rec in self:
            rec.subtotal = rec.quantity * rec.unit_price
    


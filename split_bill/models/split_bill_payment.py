# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SplitBillPayment(models.Model):
    _name = 'split.bill.payment'
    _description = 'Split Bill Payment'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                       default=lambda self: _('New'))
    participant_id = fields.Many2one('split.bill.participant', string='Participant', required=True, 
                                     ondelete='cascade')
    bill_id = fields.Many2one('split.bill', related='participant_id.bill_id', store=True)
    
    # Related fields
    currency_id = fields.Many2one(related='participant_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='participant_id.company_id', string='Company')
    
    # Payment information
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Credit/Debit Card'),
        ('online', 'Online Payment'),
        ('mobile', 'Mobile Payment'),
        ('other', 'Other'),
    ], string='Payment Method', required=True)
    payment_reference = fields.Char(string='Payment Reference')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')
    
    # Notes
    note = fields.Text(string='Note')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('split.bill.payment') or _('New')
        return super(SplitBillPayment, self).create(vals_list)
    
    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))
    
    def action_confirm(self):
        """Confirm the payment"""
        for payment in self:
            # Update participant's paid amount
            participant = payment.participant_id
            participant.amount_paid += payment.amount
            
            payment.state = 'confirmed'
        return True
    
    def action_cancel(self):
        """Cancel the payment"""
        for payment in self:
            if payment.state == 'confirmed':
                # Revert participant's paid amount
                participant = payment.participant_id
                participant.amount_paid -= payment.amount
                
            payment.state = 'cancelled'
        return True
    
    def action_draft(self):
        """Reset to draft"""
        for payment in self:
            if payment.state == 'cancelled' and payment.participant_id:
                payment.state = 'draft'
        return True

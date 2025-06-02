# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SplitBillPaymentWizard(models.TransientModel):
    _name = 'split.bill.payment.wizard'
    _description = 'Split Bill Payment Wizard'

    participant_id = fields.Many2one('split.bill.participant', string='Participant', required=True)
    
    # Related fields
    bill_id = fields.Many2one('split.bill', related='participant_id.bill_id', string='Bill')
    partner_id = fields.Many2one('res.partner', related='participant_id.partner_id', string='Partner')
    currency_id = fields.Many2one(related='participant_id.currency_id', string='Currency')
    
    # Payment information
    amount_total = fields.Monetary(related='participant_id.amount_total', string='Total Amount')
    amount_paid = fields.Monetary(related='participant_id.amount_paid', string='Amount Paid')
    amount_due = fields.Monetary(related='participant_id.amount_due', string='Amount Due')
    
    amount = fields.Monetary(string='Payment Amount', required=True)
    payment_date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Credit/Debit Card'),
        ('online', 'Online Payment'),
        ('mobile', 'Mobile Payment'),
        ('other', 'Other'),
    ], string='Payment Method', required=True, default='cash')
    payment_reference = fields.Char(string='Payment Reference')
    note = fields.Text(string='Note')
    
    @api.model
    def default_get(self, fields):
        res = super(SplitBillPaymentWizard, self).default_get(fields)
        
        if 'participant_id' in fields and not res.get('participant_id'):
            if self._context.get('active_model') == 'split.bill.participant':
                res['participant_id'] = self._context.get('active_id')
                
        if res.get('participant_id'):
            participant = self.env['split.bill.participant'].browse(res['participant_id'])
            if 'amount' in fields:
                res['amount'] = participant.amount_due
                
        return res
    
    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))
    
    def action_register_payment(self):
        """Register the payment"""
        self.ensure_one()
        
        if not self.participant_id:
            raise UserError(_('No participant selected.'))
            
        # Create payment
        payment = self.env['split.bill.payment'].create({
            'participant_id': self.participant_id.id,
            'date': self.payment_date,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'payment_reference': self.payment_reference,
            'note': self.note,
        })
        
        # Confirm payment
        payment.action_confirm()
        
        return {
            'type': 'ir.actions.act_window_close',
            'infos': {
                'title': _('Payment Registered'),
                'message': _('Payment of %s %s has been registered.') % (
                    self.amount, self.currency_id.symbol),
                'type': 'success',
            }
        }

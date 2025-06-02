# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SplitBillParticipant(models.Model):
    _name = 'split.bill.participant'
    _description = 'Split Bill Participant'
    _rec_name = 'partner_id'

    bill_id = fields.Many2one('split.bill', string='Bill', ondelete='cascade')
    session_id = fields.Many2one('split.bill.session', string='Session', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Participant', required=True)
    
    # Related fields
    currency_id = fields.Many2one(related='bill_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='bill_id.company_id', string='Company')
    
    # Split information
    split_percentage = fields.Float(string='Split Percentage', default=0.0)
    is_payer = fields.Boolean(string='Is Payer', help='This participant paid the bill')
    
    # Amounts
    amount_subtotal = fields.Monetary(string='Subtotal Amount', default=0.0)
    delivery_fee_amount = fields.Monetary(string='Delivery Fee', default=0.0)
    discount_amount = fields.Monetary(string='Discount', default=0.0)
    amount_total = fields.Monetary(string='Total Amount', default=0.0)
    amount_paid = fields.Monetary(string='Amount Paid', default=0.0)
    amount_due = fields.Monetary(string='Amount Due', compute='_compute_amount_due')
    
    # Items
    item_ids = fields.One2many('split.bill.item', 'participant_id', string='Items')
    item_count = fields.Integer(string='Item Count', compute='_compute_item_count')
    
    # Payment information
    payment_ids = fields.One2many('split.bill.payment', 'participant_id', string='Payments')
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ], string='Payment Status', compute='_compute_payment_status')
    
    @api.depends('amount_total', 'amount_paid')
    def _compute_amount_due(self):
        for participant in self:
            participant.amount_due = participant.amount_total - participant.amount_paid
    
    @api.depends('item_ids')
    def _compute_item_count(self):
        for participant in self:
            participant.item_count = len(participant.item_ids)
    
    @api.depends('amount_total', 'amount_paid')
    def _compute_payment_status(self):
        for participant in self:
            if participant.amount_paid >= participant.amount_total:
                participant.payment_status = 'paid'
            elif participant.amount_paid > 0:
                participant.payment_status = 'partial'
            else:
                participant.payment_status = 'unpaid'
    
    @api.constrains('split_percentage')
    def _check_split_percentage(self):
        for participant in self:
            if participant.split_percentage < 0 or participant.split_percentage > 100:
                raise ValidationError(_('Split percentage must be between 0 and 100.'))
    
    def action_view_items(self):
        """View items assigned to this participant"""
        self.ensure_one()
        return {
            'name': _('Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'split.bill.item',
            'view_mode': 'tree,form',
            'domain': [('participant_id', '=', self.id)],
            'context': {'default_participant_id': self.id, 'default_bill_id': self.bill_id.id},
        }
    
    def action_register_payment(self):
        """Register a payment for this participant"""
        self.ensure_one()
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'split.bill.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_participant_id': self.id,
                'default_amount': self.amount_due,
            },
        }
    
    def action_send_reminder(self):
        """Send a payment reminder to this participant"""
        self.ensure_one()
        template = self.env.ref('split_bill.email_template_payment_reminder', raise_if_not_found=False)
        if not template:
            return
            
        template.send_mail(self.id, force_send=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminder Sent'),
                'message': _('Payment reminder sent to %s') % self.partner_id.name,
                'type': 'success',
                'sticky': False,
            }
        }


class SplitBillItemAllocation(models.Model):
    _name = 'split.bill.item.allocation'
    _description = 'Split Bill Item Allocation'
    
    session_id = fields.Many2one('split.bill.session', string='Session', required=True, ondelete='cascade')
    item_id = fields.Many2one('split.bill.item', string='Item', required=True, ondelete='cascade')
    participant_id = fields.Many2one('split.bill.participant', string='Participant', required=True, 
                                     ondelete='cascade')
    
    # Related fields
    currency_id = fields.Many2one(related='session_id.currency_id', string='Currency')
    
    # Allocation details
    quantity = fields.Float(string='Quantity', default=1.0)
    amount_subtotal = fields.Monetary(string='Subtotal Amount', required=True)
    amount_total = fields.Monetary(string='Total Amount', required=True)
    note = fields.Text(string='Note')
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for allocation in self:
            if allocation.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero.'))

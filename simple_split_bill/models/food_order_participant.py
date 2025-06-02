# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FoodOrderParticipant(models.Model):
    _name = 'food.order.participant'
    _description = 'Food Order Participant'
    _rec_name = 'partner_id'

    order_id = fields.Many2one('food.order', string='Order', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Participant', required=True)
    
    # Related fields
    currency_id = fields.Many2one(related='order_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='order_id.company_id', string='Company')
    
    # Amounts
    food_amount = fields.Monetary(string='Food Amount', default=0.0, 
                                 help="Sum of all food items assigned to this participant")
    fee_amount = fields.Monetary(string='Fee Amount', default=0.0,
                               help="Participant's share of delivery fee, service fee, and tax")
    discount_amount = fields.Monetary(string='Discount Amount', default=0.0,
                                    help="Participant's share of discounts")
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total_amount', store=True)
    
    # Payment status
    is_paid = fields.Boolean(string='Paid', default=False)
    payment_date = fields.Date(string='Payment Date')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('transfer', 'Bank Transfer'),
        ('ewallet', 'E-Wallet'),
        ('other', 'Other'),
    ], string='Payment Method')
    payment_notes = fields.Char(string='Payment Notes')
    
    # Items
    item_ids = fields.One2many('food.order.line', 'participant_id', string='Items')
    item_count = fields.Integer(string='Item Count', compute='_compute_item_count')
    
    @api.depends('food_amount', 'fee_amount', 'discount_amount')
    def _compute_total_amount(self):
        for participant in self:
            participant.total_amount = participant.food_amount + participant.fee_amount - participant.discount_amount
    
    @api.depends('item_ids')
    def _compute_item_count(self):
        for participant in self:
            participant.item_count = len(participant.item_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        participants = super(FoodOrderParticipant, self).create(vals_list)
        
        # Apply fee split method after creating participants
        orders = participants.mapped('order_id')
        for order in orders:
            order.apply_split_method()
            
        return participants
    
    def write(self, vals):
        result = super(FoodOrderParticipant, self).write(vals)
        
        # If payment status changed, check if order is fully paid
        if 'is_paid' in vals:
            orders = self.mapped('order_id')
            for order in orders:
                order._compute_payment_status()
                
        return result
    
    def unlink(self):
        orders = self.mapped('order_id')
        
        # Reassign items to avoid orphaned items
        self.mapped('item_ids').write({'participant_id': False})
        
        result = super(FoodOrderParticipant, self).unlink()
        
        # Reapply fee split method
        for order in orders:
            order.apply_split_method()
            
        return result
    
    def action_mark_as_paid(self):
        """Mark participant as paid"""
        for participant in self:
            participant.write({
                'is_paid': True,
                'payment_date': fields.Date.context_today(self),
            })
        return True
    
    def action_mark_as_unpaid(self):
        """Mark participant as unpaid"""
        for participant in self:
            participant.write({
                'is_paid': False,
                'payment_date': False,
            })
        return True
    
    def action_view_items(self):
        """View items assigned to this participant"""
        self.ensure_one()
        return {
            'name': _('Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'food.order.line',
            'view_mode': 'tree,form',
            'domain': [('participant_id', '=', self.id)],
            'context': {'default_participant_id': self.id, 'default_order_id': self.order_id.id},
        }

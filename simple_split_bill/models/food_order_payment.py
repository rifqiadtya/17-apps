# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FoodOrderPayment(models.Model):
    _name = 'food.order.payment'
    _description = 'Food Order Payment'
    _rec_name = 'partner_id'

    order_id = fields.Many2one('food.order', string='Order', required=True, ondelete='cascade')
    partner_ids = fields.Many2many('res.partner', string='Participants')
    
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
    item_ids = fields.One2many('food.order.line', 'order_id', related='order_id.line_ids', string='Items')
    item_count = fields.Integer(string='Item Count', compute='_compute_item_count')
    
    # Payment details by participant
    payment_line_ids = fields.One2many('food.order.payment.line', 'payment_id', string='Payment Lines')
    
    @api.depends('food_amount', 'fee_amount', 'discount_amount')
    def _compute_total_amount(self):
        for payment in self:
            payment.total_amount = payment.food_amount + payment.fee_amount - payment.discount_amount
    
    @api.depends('order_id.line_ids')
    def _compute_item_count(self):
        for payment in self:
            payment.item_count = len(payment.order_id.line_ids)
    
    def action_mark_as_paid(self):
        """Mark payment as paid"""
        for payment in self:
            payment.write({
                'is_paid': True,
                'payment_date': fields.Date.context_today(self),
            })
        return True
    
    def action_mark_as_unpaid(self):
        """Mark payment as unpaid"""
        for payment in self:
            payment.write({
                'is_paid': False,
                'payment_date': False,
            })
        return True
    
    def action_view_items(self):
        """View all items in this order"""
        self.ensure_one()
        return {
            'name': _('Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'food.order.line',
            'view_mode': 'tree,form',
            'domain': [('order_id', '=', self.order_id.id)],
            'context': {'default_order_id': self.order_id.id},
        }
        
    @api.model
    def create(self, vals):
        payment = super(FoodOrderPayment, self).create(vals)
        # Create payment lines for each participant
        if payment.partner_ids and not payment.payment_line_ids:
            payment._create_payment_lines()
        return payment
        
    def write(self, vals):
        result = super(FoodOrderPayment, self).write(vals)
        # If partners changed, update payment lines
        if 'partner_ids' in vals:
            self._create_payment_lines()
        return result
        
    def _create_payment_lines(self):
        """Create or update payment lines for each participant"""
        self.ensure_one()
        
        # Delete existing lines
        self.payment_line_ids.unlink()
        
        # Create new lines for each partner
        for partner in self.partner_ids:
            # Calculate food amount for this partner
            food_amount = sum(self.order_id.line_ids.filtered(lambda l: l.partner_id == partner).mapped('price_subtotal'))
            
            # Create payment line
            self.env['food.order.payment.line'].create({
                'payment_id': self.id,
                'partner_id': partner.id,
                'food_amount': food_amount,
                'fee_amount': 0.0,  # Will be updated when split method is applied
                'discount_amount': 0.0,
                'total_amount': food_amount,
            })
            
        # Apply split method
        if self.order_id:
            self.order_id.apply_split_method()
            
    def get_payment_line(self, partner):
        """Get payment line for a specific partner"""
        self.ensure_one()
        return self.payment_line_ids.filtered(lambda l: l.partner_id == partner)

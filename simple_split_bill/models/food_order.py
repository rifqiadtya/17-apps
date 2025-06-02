# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import uuid
from werkzeug.urls import url_join
from odoo.tools import consteq


class FoodOrder(models.Model):
    _name = 'food.order'
    _description = 'Food Delivery Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                       default=lambda self: _('New'))
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='company_id.currency_id', readonly=True)
    
    # Food delivery service
    service_type = fields.Selection([
        ('grab', 'Grab Food'),
        ('gofood', 'GoFood'),
        ('shopee', 'ShopeeFood'),
        ('other', 'Other'),
    ], string='Service Type', required=True, default='grab', tracking=True)
    
    # Restaurant information
    restaurant = fields.Char(string='Restaurant', required=True, tracking=True)
    
    # Order information
    subtotal = fields.Monetary(string='Food Subtotal', required=True, tracking=True)
    delivery_fee = fields.Monetary(string='Delivery Fee', default=0.0, tracking=True)
    service_fee = fields.Monetary(string='Service Fee', default=0.0, tracking=True)
    discount = fields.Monetary(string='Discount', default=0.0, tracking=True)
    tax = fields.Monetary(string='Tax', default=0.0, tracking=True)
    total = fields.Monetary(string='Total', compute='_compute_total', store=True, tracking=True)
    
    # Payment information
    payer_id = fields.Many2one('res.partner', string='Paid By', tracking=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('ewallet', 'E-Wallet'),
        ('card', 'Card'),
        ('other', 'Other'),
    ], string='Payment Method', default='cash', tracking=True)
    
    # Order lines and participants
    line_ids = fields.One2many('food.order.line', 'order_id', string='Order Lines')
    participant_ids = fields.Many2many('res.partner', string='Participants')
    
    # Participant payment information
    payment_id = fields.Many2one('food.order.payment', string='Payment')
    
    # Access token for public access
    access_token = fields.Char('Security Token', copy=False)
    public_url = fields.Char('Public URL', compute='_compute_public_url')
    
    # Split method for fees
    fee_split_method = fields.Selection([
        ('equal', 'Split Equally'),
        ('proportional', 'Split Proportionally'),
        ('payer', 'Assign to Payer'),
    ], string='Fee Split Method', default='equal', tracking=True,
       help="How to split delivery fee, service fee, and tax")
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('settled', 'Settled'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    # Statistics
    total_participants = fields.Integer(string='Participants', compute='_compute_statistics')
    total_items = fields.Integer(string='Items', compute='_compute_statistics')
    is_fully_assigned = fields.Boolean(string='Fully Assigned', compute='_compute_assignment_status')
    is_fully_paid = fields.Boolean(string='Fully Paid', compute='_compute_payment_status')
    
    # Notes
    notes = fields.Text(string='Notes')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('food.order') or _('New')
            # Generate access token
            vals['access_token'] = uuid.uuid4().hex
        return super(FoodOrder, self).create(vals_list)
        
    @api.depends('access_token')
    def _compute_public_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for order in self:
            if order.access_token:
                order.public_url = url_join(base_url, f'/food/receipt/{order.id}/{order.access_token}')
            else:
                order.public_url = False
    
    @api.depends('subtotal', 'delivery_fee', 'service_fee', 'discount', 'tax')
    def _compute_total(self):
        for order in self:
            order.total = order.subtotal + order.delivery_fee + order.service_fee + order.tax - order.discount
    
    @api.depends('participant_ids', 'line_ids')
    def _compute_statistics(self):
        for order in self:
            order.total_participants = len(order.participant_ids)
            order.total_items = len(order.line_ids)
    
    @api.depends('line_ids.partner_id')
    def _compute_assignment_status(self):
        for order in self:
            if not order.line_ids:
                order.is_fully_assigned = False
            else:
                order.is_fully_assigned = all(line.partner_id for line in order.line_ids)
    
    @api.depends('payment_id.is_paid')
    def _compute_payment_status(self):
        for order in self:
            if not order.payment_id or not order.participant_ids:
                order.is_fully_paid = False
            else:
                order.is_fully_paid = order.payment_id.is_paid
    
    def action_confirm(self):
        """Confirm the food order"""
        for order in self:
            if order.state != 'draft':
                continue
                
            if not order.line_ids:
                raise UserError(_('You must add at least one order line.'))
                
            order.state = 'confirmed'
        return True
    
    def action_settle(self):
        """Mark the order as settled"""
        for order in self:
            if order.state != 'confirmed':
                continue
                
            if not order.is_fully_assigned:
                raise UserError(_('All items must be assigned to participants before settling.'))
                
            # Nothing to do for payment status as it's handled by the payment_ids
                
            order.state = 'settled'
        return True
    
    def action_cancel(self):
        """Cancel the food order"""
        for order in self:
            if order.state in ['settled']:
                raise UserError(_('Cannot cancel a settled order.'))
                
            order.state = 'cancelled'
        return True
    
    def action_draft(self):
        """Reset to draft"""
        for order in self:
            if order.state != 'cancelled':
                continue
                
            order.state = 'draft'
        return True
    
    def action_assign_items(self):
        """Open wizard to assign items to participants"""
        self.ensure_one()
        
        # Check if there are participants
        if not self.participant_ids:
            raise UserError(_('You must add participants before assigning items.'))
            
        # Check if there are items
        if not self.line_ids:
            raise UserError(_('You must add order lines before assigning items.'))
            
        return {
            'name': _('Assign Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'food.order.line',
            'view_mode': 'tree,form',
            'domain': [('order_id', '=', self.id)],
            'context': {'default_order_id': self.id},
            'target': 'current',
        }
    
    def action_view_payment(self):
        """View payment"""
        self.ensure_one()
        if not self.payment_id:
            return {
                'name': _('Create Payment'),
                'type': 'ir.actions.act_window',
                'res_model': 'food.order.payment',
                'view_mode': 'form',
                'context': {'default_order_id': self.id},
                'target': 'current',
            }
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'food.order.payment',
            'view_mode': 'form',
            'res_id': self.payment_id.id,
            'context': {'default_order_id': self.id},
            'target': 'current',
        }
        
    def generate_new_token(self):
        """Generate a new access token"""
        for order in self:
            order.access_token = uuid.uuid4().hex
        return True
        
    def action_view_receipt(self):
        """Open the public receipt URL in a new browser tab"""
        self.ensure_one()
        if not self.public_url:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No public URL available'),
                    'message': _('Please generate an access token first.'),
                    'sticky': False,
                    'type': 'warning',
                }
            }
        return {
            'type': 'ir.actions.act_url',
            'url': self.public_url,
            'target': 'new',
        }
        
    def check_access_token(self, token):
        """Check if the provided token is valid"""
        self.ensure_one()
        return consteq(self.access_token, token)
    
    def split_fees_equally(self):
        """Split fees equally among participants"""
        self.ensure_one()
        if not self.participant_ids:
            return
            
        # Calculate fee per participant
        total_fee = self.delivery_fee + self.service_fee + self.tax
        participant_count = len(self.participant_ids)
        fee_per_participant = total_fee / participant_count if participant_count else 0
        
        # Get or create payment
        payment = self._get_or_create_payment()
        
        # Update payment lines
        for line in payment.payment_line_ids:
            # Calculate food amount for this participant
            food_amount = sum(self.line_ids.filtered(lambda l: l.partner_id == line.partner_id).mapped('price_subtotal'))
            
            # Update payment line
            line.write({
                'food_amount': food_amount,
                'fee_amount': fee_per_participant,
                'total_amount': food_amount + fee_per_participant - line.discount_amount
            })
    
    def split_fees_proportionally(self):
        """Split fees proportionally based on food amount"""
        self.ensure_one()
        if not self.participant_ids:
            return
            
        # Calculate total food amount
        total_food_amount = self.subtotal
        if not total_food_amount:
            return self.split_fees_equally()
            
        # Calculate total fee
        total_fee = self.delivery_fee + self.service_fee + self.tax
        
        # Get or create payment
        payment = self._get_or_create_payment()
        
        # Update payment lines
        for line in payment.payment_line_ids:
            # Calculate food amount for this participant
            food_amount = sum(self.line_ids.filtered(lambda l: l.partner_id == line.partner_id).mapped('price_subtotal'))
            
            # Calculate proportional fee
            proportion = food_amount / total_food_amount if total_food_amount else 0
            fee_amount = total_fee * proportion
            
            # Update payment line
            line.write({
                'food_amount': food_amount,
                'fee_amount': fee_amount,
                'total_amount': food_amount + fee_amount - line.discount_amount
            })
    
    def assign_fees_to_payer(self):
        """Assign all fees to the payer"""
        self.ensure_one()
        if not self.participant_ids or not self.payer_id:
            return
            
        # Calculate total fee
        total_fee = self.delivery_fee + self.service_fee + self.tax
        
        # Get or create payment
        payment = self._get_or_create_payment()
        
        # Update payment lines
        for line in payment.payment_line_ids:
            # Calculate food amount for this participant
            food_amount = sum(self.line_ids.filtered(lambda l: l.partner_id == line.partner_id).mapped('price_subtotal'))
            
            # Determine fee amount
            fee_amount = total_fee if line.partner_id == self.payer_id else 0.0
            
            # Update payment line
            line.write({
                'food_amount': food_amount,
                'fee_amount': fee_amount,
                'total_amount': food_amount + fee_amount - line.discount_amount
            })
    
    def _get_or_create_payment(self):
        """Get or create payment record"""
        if not self.payment_id:
            payment = self.env['food.order.payment'].create({
                'order_id': self.id,
                'partner_ids': [(6, 0, self.participant_ids.ids)],
            })
            self.payment_id = payment.id
        return self.payment_id
    
    def apply_split_method(self):
        """Apply the selected fee split method"""
        self.ensure_one()
        
        if self.fee_split_method == 'equal':
            self.split_fees_equally()
        elif self.fee_split_method == 'proportional':
            self.split_fees_proportionally()
        elif self.fee_split_method == 'payer':
            self.assign_fees_to_payer()
            
        return True

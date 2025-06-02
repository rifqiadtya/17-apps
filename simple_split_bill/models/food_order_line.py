# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FoodOrderLine(models.Model):
    _name = 'food.order.line'
    _description = 'Food Order Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    order_id = fields.Many2one('food.order', string='Order', required=True, ondelete='cascade')
    
    # Related fields
    currency_id = fields.Many2one(related='order_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='order_id.company_id', string='Company')
    
    # Item information
    name = fields.Char(string='Item', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Monetary(string='Unit Price', required=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price', store=True)
    
    # Participant assignment
    partner_id = fields.Many2one('res.partner', string='Assigned To',
                                domain="[('id', 'in', parent.participant_ids)]")
    is_assigned = fields.Boolean(string='Assigned', compute='_compute_is_assigned', store=True)
    
    # Notes
    notes = fields.Char(string='Notes')
    
    @api.depends('quantity', 'price_unit')
    def _compute_price(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
    
    @api.depends('partner_id')
    def _compute_is_assigned(self):
        for line in self:
            line.is_assigned = bool(line.partner_id)
    
    @api.model_create_multi
    def create(self, vals_list):
        lines = super(FoodOrderLine, self).create(vals_list)
        # Update order subtotal
        orders = lines.mapped('order_id')
        for order in orders:
            order.subtotal = sum(order.line_ids.mapped('price_subtotal'))
        return lines
    
    def write(self, vals):
        result = super(FoodOrderLine, self).write(vals)
        # Update order subtotal if price or quantity changed
        if 'price_unit' in vals or 'quantity' in vals:
            orders = self.mapped('order_id')
            for order in orders:
                order.subtotal = sum(order.line_ids.mapped('price_subtotal'))
        
        # Update order payment records if partner changed
        if 'partner_id' in vals:
            orders = self.mapped('order_id')
            for order in orders:
                order.apply_split_method()
        
        return result
    
    def unlink(self):
        orders = self.mapped('order_id')
        partners = self.mapped('partner_id')
        result = super(FoodOrderLine, self).unlink()
        
        # Update order subtotal
        for order in orders:
            order.subtotal = sum(order.line_ids.mapped('price_subtotal'))
        
        # Update order payment records
        for order in orders:
            order.apply_split_method()
        
        return result
    
    def action_assign_to_partner(self, partner_id):
        """Assign this line to a partner"""
        self.ensure_one()
        
        if not partner_id:
            return False
            
        self.partner_id = partner_id
        return True

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SplitBillItem(models.Model):
    _name = 'split.bill.item'
    _description = 'Split Bill Item'
    _order = 'sequence, id'

    bill_id = fields.Many2one('split.bill', string='Bill', required=True, ondelete='cascade')
    participant_id = fields.Many2one('split.bill.participant', string='Participant', ondelete='set null')
    
    # Related fields
    currency_id = fields.Many2one(related='bill_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='bill_id.company_id', string='Company')
    
    # Item information
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Description', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    
    # Taxes and discounts
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_amounts')
    discount = fields.Float(string='Discount (%)', default=0.0)
    discount_amount = fields.Monetary(string='Discount Amount', compute='_compute_amounts')
    
    # Computed amounts
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_amounts', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_amounts', store=True)
    
    # Split information
    is_split = fields.Boolean(string='Is Split', compute='_compute_is_split')
    split_type = fields.Selection([
        ('single', 'Single Participant'),
        ('multiple', 'Multiple Participants'),
        ('equal', 'Equal Split'),
        ('custom', 'Custom Split'),
    ], string='Split Type', default='single')
    
    # For multiple participant splits
    participant_ids = fields.Many2many('split.bill.participant', 'split_bill_item_participant_rel',
                                       'item_id', 'participant_id', string='Participants')
    
    # For tracking allocations
    allocation_ids = fields.One2many('split.bill.item.allocation', 'item_id', string='Allocations')
    allocated_quantity = fields.Float(string='Allocated Quantity', compute='_compute_allocated')
    allocated_amount = fields.Monetary(string='Allocated Amount', compute='_compute_allocated')
    is_fully_allocated = fields.Boolean(string='Fully Allocated', compute='_compute_allocated')
    
    # Notes
    note = fields.Text(string='Note')
    
    @api.depends('quantity', 'price_unit', 'tax_ids', 'discount')
    def _compute_amounts(self):
        """Compute the amounts of the item line."""
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.discount_amount = line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
            
            taxes = line.tax_ids.compute_all(
                price, line.currency_id, line.quantity, 
                product=line.product_id, partner=line.participant_id.partner_id
            )
            
            line.price_subtotal = taxes['total_excluded']
            line.price_total = taxes['total_included']
            line.tax_amount = line.price_total - line.price_subtotal
    
    @api.depends('participant_id', 'participant_ids', 'split_type')
    def _compute_is_split(self):
        for item in self:
            if item.split_type == 'single':
                item.is_split = bool(item.participant_id)
            else:
                item.is_split = bool(item.participant_ids)
    
    @api.depends('allocation_ids.quantity', 'allocation_ids.amount_subtotal', 'quantity', 'price_subtotal')
    def _compute_allocated(self):
        for item in self:
            item.allocated_quantity = sum(item.allocation_ids.mapped('quantity'))
            item.allocated_amount = sum(item.allocation_ids.mapped('amount_subtotal'))
            
            item.is_fully_allocated = (
                item.allocated_quantity >= item.quantity and
                abs(item.allocated_amount - item.price_subtotal) < 0.01
            )
    
    @api.constrains('discount')
    def _check_discount(self):
        for line in self:
            if line.discount < 0 or line.discount > 100:
                raise ValidationError(_('Discount must be between 0 and 100.'))
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
            
        self.name = self.product_id.name
        self.price_unit = self.product_id.lst_price
        
        # Set taxes
        fpos = self.bill_id.partner_id.property_account_position_id
        taxes = self.product_id.taxes_id
        
        if fpos:
            taxes = fpos.map_tax(taxes)
            
        self.tax_ids = [(6, 0, taxes.ids)]
    
    def split_equally(self, participant_ids):
        """Split this item equally among the given participants"""
        self.ensure_one()
        
        if not participant_ids:
            return False
            
        participants = self.env['split.bill.participant'].browse(participant_ids)
        if not participants:
            return False
            
        # Set split type
        self.write({
            'split_type': 'equal',
            'participant_ids': [(6, 0, participant_ids)],
        })
        
        # Create allocations
        session = self.bill_id.active_session_id
        if not session:
            return False
            
        # Remove existing allocations
        self.allocation_ids.filtered(lambda a: a.session_id == session).unlink()
        
        # Create new allocations
        num_participants = len(participants)
        quantity_per_person = self.quantity / num_participants
        amount_per_person = self.price_subtotal / num_participants
        total_per_person = self.price_total / num_participants
        
        for participant in participants:
            self.env['split.bill.item.allocation'].create({
                'session_id': session.id,
                'item_id': self.id,
                'participant_id': participant.id,
                'quantity': quantity_per_person,
                'amount_subtotal': amount_per_person,
                'amount_total': total_per_person,
            })
            
        return True
    
    def split_custom(self, allocations):
        """Split this item with custom allocations
        
        Args:
            allocations: list of dicts with keys:
                - participant_id: ID of the participant
                - quantity: Quantity to allocate
                - amount_subtotal: Subtotal amount to allocate (optional)
                - amount_total: Total amount to allocate (optional)
        """
        self.ensure_one()
        
        if not allocations:
            return False
            
        # Set split type
        self.write({
            'split_type': 'custom',
            'participant_ids': [(6, 0, [a['participant_id'] for a in allocations])],
        })
        
        # Create allocations
        session = self.bill_id.active_session_id
        if not session:
            return False
            
        # Remove existing allocations
        self.allocation_ids.filtered(lambda a: a.session_id == session).unlink()
        
        # Create new allocations
        for allocation in allocations:
            # Calculate amounts if not provided
            if 'amount_subtotal' not in allocation:
                ratio = allocation['quantity'] / self.quantity if self.quantity else 0
                amount_subtotal = self.price_subtotal * ratio
                amount_total = self.price_total * ratio
            else:
                amount_subtotal = allocation['amount_subtotal']
                amount_total = allocation.get('amount_total', amount_subtotal)
                
            self.env['split.bill.item.allocation'].create({
                'session_id': session.id,
                'item_id': self.id,
                'participant_id': allocation['participant_id'],
                'quantity': allocation['quantity'],
                'amount_subtotal': amount_subtotal,
                'amount_total': amount_total,
            })
            
        return True
    
    def assign_to_participant(self, participant_id):
        """Assign this item to a single participant"""
        self.ensure_one()
        
        if not participant_id:
            return False
            
        participant = self.env['split.bill.participant'].browse(participant_id)
        if not participant:
            return False
            
        # Set split type
        self.write({
            'split_type': 'single',
            'participant_id': participant_id,
            'participant_ids': [(5, 0, 0)],  # Clear many2many
        })
        
        # Create allocation
        session = self.bill_id.active_session_id
        if not session:
            return False
            
        # Remove existing allocations
        self.allocation_ids.filtered(lambda a: a.session_id == session).unlink()
        
        # Create new allocation
        self.env['split.bill.item.allocation'].create({
            'session_id': session.id,
            'item_id': self.id,
            'participant_id': participant_id,
            'quantity': self.quantity,
            'amount_subtotal': self.price_subtotal,
            'amount_total': self.price_total,
        })
            
        return True

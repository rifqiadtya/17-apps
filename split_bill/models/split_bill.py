# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
import json


class SplitBill(models.Model):
    _name = 'split.bill'
    _description = 'Split Bill'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                       default=lambda self: _('New'))
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='company_id.currency_id', readonly=True)
    
    # Related documents
    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    
    # Bill information
    total_amount = fields.Monetary(string='Total Amount', required=True)
    subtotal_amount = fields.Monetary(string='Subtotal Amount', compute='_compute_amounts')
    tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_amounts')
    discount_amount = fields.Monetary(string='Discount Amount')
    delivery_fee = fields.Monetary(string='Delivery Fee')
    
    # Split information
    session_ids = fields.One2many('split.bill.session', 'bill_id', string='Split Sessions')
    active_session_id = fields.Many2one('split.bill.session', string='Active Session')
    participant_ids = fields.One2many('split.bill.participant', 'bill_id', string='Participants')
    item_ids = fields.One2many('split.bill.item', 'bill_id', string='Items')
    
    # Split methods
    split_method = fields.Selection([
        ('equal', 'Split Equally'),
        ('amount', 'Split by Amount'),
        ('percentage', 'Split by Percentage'),
        ('item', 'Split by Items'),
        ('custom', 'Custom Split'),
    ], string='Split Method', default='equal')
    
    # Delivery fee split method
    delivery_fee_split_method = fields.Selection([
        ('equal', 'Split Equally'),
        ('proportional', 'Split Proportionally'),
        ('payer', 'Assign to Payer'),
        ('exclude', 'Exclude from Split'),
    ], string='Delivery Fee Split Method', default='equal')
    
    # Discount split method
    discount_split_method = fields.Selection([
        ('equal', 'Split Equally'),
        ('proportional', 'Split Proportionally'),
        ('item_specific', 'Item Specific'),
    ], string='Discount Split Method', default='proportional')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    # Computed fields
    total_participants = fields.Integer(string='Total Participants', compute='_compute_participants')
    is_fully_paid = fields.Boolean(string='Is Fully Paid', compute='_compute_payment_status')
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ], string='Payment Status', compute='_compute_payment_status')
    
    # JSON field to store complex splitting configuration
    split_config = fields.Text(string='Split Configuration', help='JSON configuration for complex splits')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('split.bill') or _('New')
        return super(SplitBill, self).create(vals_list)
    
    @api.depends('item_ids.price_subtotal', 'item_ids.tax_amount')
    def _compute_amounts(self):
        for bill in self:
            bill.subtotal_amount = sum(bill.item_ids.mapped('price_subtotal'))
            bill.tax_amount = sum(bill.item_ids.mapped('tax_amount'))
    
    @api.depends('participant_ids')
    def _compute_participants(self):
        for bill in self:
            bill.total_participants = len(bill.participant_ids)
    
    @api.depends('participant_ids.amount_paid', 'participant_ids.amount_total')
    def _compute_payment_status(self):
        for bill in self:
            total_to_pay = sum(bill.participant_ids.mapped('amount_total'))
            total_paid = sum(bill.participant_ids.mapped('amount_paid'))
            
            if total_paid >= total_to_pay and total_to_pay > 0:
                bill.is_fully_paid = True
                bill.payment_status = 'paid'
            elif total_paid > 0:
                bill.is_fully_paid = False
                bill.payment_status = 'partial'
            else:
                bill.is_fully_paid = False
                bill.payment_status = 'unpaid'
    
    def action_create_session(self):
        """Create a new split session"""
        self.ensure_one()
        if self.state == 'draft':
            self.state = 'in_progress'
        
        session = self.env['split.bill.session'].create({
            'bill_id': self.id,
            'name': f"Session {len(self.session_ids) + 1}",
        })
        
        self.active_session_id = session.id
        return {
            'name': _('Split Bill Session'),
            'type': 'ir.actions.act_window',
            'res_model': 'split.bill.session',
            'view_mode': 'form',
            'res_id': session.id,
            'target': 'new',
        }
    
    def action_split_bill(self):
        """Open the split bill wizard"""
        self.ensure_one()
        return {
            'name': _('Split Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'split.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_bill_id': self.id},
        }
    
    def action_confirm(self):
        """Confirm the bill split"""
        self.ensure_one()
        if not self.participant_ids:
            raise UserError(_('You must add participants to split the bill.'))
        if not self.item_ids:
            raise UserError(_('You must add items to split the bill.'))
        
        # Validate the split
        total_allocated = sum(self.participant_ids.mapped('amount_total'))
        if float_round(total_allocated, 2) != float_round(self.total_amount, 2):
            raise ValidationError(_(
                'The total allocated amount (%s) does not match the bill total (%s).'
            ) % (total_allocated, self.total_amount))
        
        self.state = 'completed'
        return True
    
    def action_cancel(self):
        """Cancel the bill split"""
        self.ensure_one()
        self.state = 'cancelled'
        return True
    
    def action_reset_to_draft(self):
        """Reset the bill to draft"""
        self.ensure_one()
        self.state = 'draft'
        return True
    
    def apply_equal_split(self):
        """Split the bill equally among participants"""
        self.ensure_one()
        if not self.participant_ids:
            raise UserError(_('You must add participants to split the bill.'))
        
        num_participants = len(self.participant_ids)
        if num_participants == 0:
            return
        
        base_amount_per_person = self.subtotal_amount / num_participants
        
        # Handle delivery fee based on selected method
        delivery_fee_per_person = 0
        if self.delivery_fee > 0:
            if self.delivery_fee_split_method == 'equal':
                delivery_fee_per_person = self.delivery_fee / num_participants
            elif self.delivery_fee_split_method == 'proportional':
                # Will be calculated per participant based on their items
                pass
            elif self.delivery_fee_split_method == 'payer':
                # Will be assigned to a specific participant
                pass
        
        # Handle discount based on selected method
        discount_per_person = 0
        if self.discount_amount > 0:
            if self.discount_split_method == 'equal':
                discount_per_person = self.discount_amount / num_participants
            elif self.discount_split_method == 'proportional':
                # Will be calculated per participant based on their items
                pass
        
        # Update each participant's amount
        for participant in self.participant_ids:
            participant.write({
                'amount_subtotal': base_amount_per_person,
                'delivery_fee_amount': delivery_fee_per_person,
                'discount_amount': discount_per_person,
                'amount_total': base_amount_per_person + delivery_fee_per_person - discount_per_person,
            })
    
    def apply_item_split(self):
        """Split the bill by items"""
        self.ensure_one()
        if not self.participant_ids or not self.item_ids:
            raise UserError(_('You must add participants and items to split the bill.'))
        
        # Reset participant amounts
        self.participant_ids.write({
            'amount_subtotal': 0,
            'delivery_fee_amount': 0,
            'discount_amount': 0,
            'amount_total': 0,
        })
        
        # Calculate each participant's share based on their items
        for item in self.item_ids:
            if item.participant_id:
                participant = item.participant_id
                participant.amount_subtotal += item.price_subtotal
                participant.amount_total += item.price_total
        
        # Handle delivery fee based on selected method
        if self.delivery_fee > 0:
            if self.delivery_fee_split_method == 'equal':
                fee_per_person = self.delivery_fee / len(self.participant_ids)
                for participant in self.participant_ids:
                    participant.delivery_fee_amount = fee_per_person
                    participant.amount_total += fee_per_person
            elif self.delivery_fee_split_method == 'proportional':
                total_items_amount = sum(self.item_ids.mapped('price_subtotal'))
                for participant in self.participant_ids:
                    if total_items_amount > 0:
                        proportion = participant.amount_subtotal / total_items_amount
                        fee_amount = self.delivery_fee * proportion
                        participant.delivery_fee_amount = fee_amount
                        participant.amount_total += fee_amount
        
        # Handle discount based on selected method
        if self.discount_amount > 0:
            if self.discount_split_method == 'equal':
                discount_per_person = self.discount_amount / len(self.participant_ids)
                for participant in self.participant_ids:
                    participant.discount_amount = discount_per_person
                    participant.amount_total -= discount_per_person
            elif self.discount_split_method == 'proportional':
                total_items_amount = sum(self.item_ids.mapped('price_subtotal'))
                for participant in self.participant_ids:
                    if total_items_amount > 0:
                        proportion = participant.amount_subtotal / total_items_amount
                        discount_amount = self.discount_amount * proportion
                        participant.discount_amount = discount_amount
                        participant.amount_total -= discount_amount
            elif self.discount_split_method == 'item_specific':
                # Discounts are already applied at the item level
                for participant in self.participant_ids:
                    participant.discount_amount = sum(
                        item.discount_amount for item in self.item_ids if item.participant_id == participant
                    )
    
    def apply_percentage_split(self):
        """Split the bill by percentage"""
        self.ensure_one()
        if not self.participant_ids:
            raise UserError(_('You must add participants to split the bill.'))
        
        total_percentage = sum(self.participant_ids.mapped('split_percentage'))
        if total_percentage != 100:
            raise ValidationError(_('The total percentage must be 100%.'))
        
        for participant in self.participant_ids:
            percentage = participant.split_percentage / 100
            participant.amount_subtotal = self.subtotal_amount * percentage
            
            # Handle delivery fee
            if self.delivery_fee > 0:
                if self.delivery_fee_split_method == 'equal':
                    participant.delivery_fee_amount = self.delivery_fee / len(self.participant_ids)
                elif self.delivery_fee_split_method == 'proportional':
                    participant.delivery_fee_amount = self.delivery_fee * percentage
            
            # Handle discount
            if self.discount_amount > 0:
                if self.discount_split_method == 'equal':
                    participant.discount_amount = self.discount_amount / len(self.participant_ids)
                elif self.discount_split_method == 'proportional':
                    participant.discount_amount = self.discount_amount * percentage
            
            # Calculate total
            participant.amount_total = (
                participant.amount_subtotal + 
                participant.delivery_fee_amount - 
                participant.discount_amount
            )
    
    def apply_custom_split(self):
        """Apply a custom split based on the split_config JSON field"""
        self.ensure_one()
        if not self.split_config:
            raise UserError(_('No custom split configuration defined.'))
        
        try:
            config = json.loads(self.split_config)
            
            # Reset participant amounts
            self.participant_ids.write({
                'amount_subtotal': 0,
                'delivery_fee_amount': 0,
                'discount_amount': 0,
                'amount_total': 0,
            })
            
            # Apply custom configuration
            for participant_data in config.get('participants', []):
                participant_id = participant_data.get('id')
                participant = self.participant_ids.filtered(lambda p: p.id == participant_id)
                if participant:
                    participant.write({
                        'amount_subtotal': participant_data.get('subtotal', 0),
                        'delivery_fee_amount': participant_data.get('delivery_fee', 0),
                        'discount_amount': participant_data.get('discount', 0),
                        'amount_total': participant_data.get('total', 0),
                    })
                    
                    # Assign items if specified
                    for item_id in participant_data.get('item_ids', []):
                        item = self.item_ids.filtered(lambda i: i.id == item_id)
                        if item:
                            item.participant_id = participant.id
            
        except (ValueError, KeyError) as e:
            raise UserError(_('Invalid custom split configuration: %s') % str(e))
    
    def import_from_sale_order(self):
        """Import items from a linked sales order"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No sales order linked to this bill.'))
        
        order = self.sale_order_id
        
        # Import items
        for line in order.order_line:
            self.env['split.bill.item'].create({
                'bill_id': self.id,
                'name': line.name,
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_id.ids)],
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_total,
            })
        
        # Update bill amounts
        self.total_amount = order.amount_total
        self.discount_amount = sum((line.price_unit * line.product_uom_qty * line.discount / 100) 
                                  for line in order.order_line)
        
        return True
    
    def import_from_invoice(self):
        """Import items from a linked invoice"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No invoice linked to this bill.'))
        
        invoice = self.invoice_id
        
        # Import items
        for line in invoice.invoice_line_ids:
            self.env['split.bill.item'].create({
                'bill_id': self.id,
                'name': line.name,
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_total,
            })
        
        # Update bill amounts
        self.total_amount = invoice.amount_total
        self.discount_amount = sum((line.price_unit * line.quantity * line.discount / 100) 
                                  for line in invoice.invoice_line_ids)
        
        return True
    
    def import_from_pos_order(self):
        """Import items from a linked POS order"""
        self.ensure_one()
        if not self.pos_order_id:
            raise UserError(_('No POS order linked to this bill.'))
        
        order = self.pos_order_id
        
        # Import items
        for line in order.lines:
            self.env['split.bill.item'].create({
                'bill_id': self.id,
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'quantity': line.qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_subtotal_incl,
            })
        
        # Update bill amounts
        self.total_amount = order.amount_total
        self.discount_amount = sum((line.price_unit * line.qty * line.discount / 100) 
                                  for line in order.lines)
        
        return True

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SplitBillSession(models.Model):
    _name = 'split.bill.session'
    _description = 'Split Bill Session'
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True)
    bill_id = fields.Many2one('split.bill', string='Bill', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    
    # Related fields
    currency_id = fields.Many2one(related='bill_id.currency_id')
    company_id = fields.Many2one(related='bill_id.company_id')
    
    # Session data
    participant_ids = fields.One2many('split.bill.participant', 'session_id', string='Participants')
    item_allocation_ids = fields.One2many('split.bill.item.allocation', 'session_id', 
                                          string='Item Allocations')
    
    # Split method used in this session
    split_method = fields.Selection(related='bill_id.split_method', string='Split Method')
    
    # Session status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')
    
    # Session results
    result_summary = fields.Text(string='Result Summary', readonly=True)
    
    def action_start(self):
        """Start the split session"""
        self.ensure_one()
        self.state = 'in_progress'
        return True
    
    def action_complete(self):
        """Complete the split session"""
        self.ensure_one()
        
        # Validate session data
        if not self.participant_ids:
            raise UserError(_('You must add participants to complete the session.'))
        
        # Apply the split to the bill
        self._apply_split_to_bill()
        
        # Generate result summary
        self._generate_result_summary()
        
        self.state = 'completed'
        return True
    
    def action_cancel(self):
        """Cancel the split session"""
        self.ensure_one()
        self.state = 'cancelled'
        return True
    
    def _apply_split_to_bill(self):
        """Apply the session's split to the bill"""
        self.ensure_one()
        bill = self.bill_id
        
        # Copy participants from session to bill if they don't exist
        for session_participant in self.participant_ids:
            if not bill.participant_ids.filtered(lambda p: p.partner_id == session_participant.partner_id):
                session_participant.copy({
                    'bill_id': bill.id,
                    'session_id': False,
                })
        
        # Apply item allocations
        for allocation in self.item_allocation_ids:
            item = allocation.item_id
            participant = allocation.participant_id
            
            # Find or create the corresponding bill participant
            bill_participant = bill.participant_ids.filtered(
                lambda p: p.partner_id == participant.partner_id
            )
            
            if bill_participant:
                # Update the item's participant
                item.participant_id = bill_participant.id
                
                # Update participant amounts
                bill_participant.amount_subtotal += allocation.amount_subtotal
                bill_participant.amount_total += allocation.amount_total
    
    def _generate_result_summary(self):
        """Generate a summary of the split results"""
        self.ensure_one()
        bill = self.bill_id
        
        summary_lines = [_('Split Bill Session Summary')]
        summary_lines.append('=' * 40)
        summary_lines.append(_('Split Method: %s') % dict(bill._fields['split_method'].selection).get(bill.split_method))
        summary_lines.append(_('Total Amount: %s %s') % (bill.total_amount, bill.currency_id.symbol))
        summary_lines.append('=' * 40)
        
        # Participant breakdown
        summary_lines.append(_('Participant Breakdown:'))
        for participant in bill.participant_ids:
            summary_lines.append(_('- %s: %s %s') % (
                participant.partner_id.name,
                participant.amount_total,
                bill.currency_id.symbol
            ))
        
        self.result_summary = '\n'.join(summary_lines)
    
    def add_participant(self, partner_id, percentage=None):
        """Add a participant to the session"""
        self.ensure_one()
        
        # Check if participant already exists
        existing = self.participant_ids.filtered(lambda p: p.partner_id.id == partner_id)
        if existing:
            return existing
        
        # Create new participant
        values = {
            'session_id': self.id,
            'partner_id': partner_id,
        }
        
        if percentage is not None:
            values['split_percentage'] = percentage
            
        return self.env['split.bill.participant'].create(values)
    
    def allocate_item(self, item_id, participant_id, quantity=None, amount=None):
        """Allocate an item to a participant"""
        self.ensure_one()
        
        item = self.env['split.bill.item'].browse(item_id)
        if not item or item.bill_id != self.bill_id:
            raise UserError(_('Invalid item for this bill.'))
        
        participant = self.env['split.bill.participant'].browse(participant_id)
        if not participant or participant.session_id != self:
            raise UserError(_('Invalid participant for this session.'))
        
        # Determine allocation quantity and amount
        if quantity is None:
            quantity = item.quantity
            
        if amount is None:
            # Proportional to quantity
            ratio = quantity / item.quantity if item.quantity else 0
            amount_subtotal = item.price_subtotal * ratio
            amount_total = item.price_total * ratio
        else:
            amount_subtotal = amount
            # Estimate total with taxes
            tax_ratio = item.price_total / item.price_subtotal if item.price_subtotal else 1
            amount_total = amount * tax_ratio
        
        # Create allocation
        return self.env['split.bill.item.allocation'].create({
            'session_id': self.id,
            'item_id': item.id,
            'participant_id': participant.id,
            'quantity': quantity,
            'amount_subtotal': amount_subtotal,
            'amount_total': amount_total,
        })
    
    def apply_equal_split(self):
        """Split all items equally among participants"""
        self.ensure_one()
        
        if not self.participant_ids:
            raise UserError(_('You must add participants to split the bill.'))
            
        bill = self.bill_id
        participants = self.participant_ids
        num_participants = len(participants)
        
        # Split each item equally
        for item in bill.item_ids:
            quantity_per_person = item.quantity / num_participants
            for participant in participants:
                self.allocate_item(item.id, participant.id, quantity_per_person)
                
        # Handle delivery fee
        if bill.delivery_fee > 0:
            if bill.delivery_fee_split_method == 'equal':
                fee_per_person = bill.delivery_fee / num_participants
                for participant in participants:
                    participant.delivery_fee_amount = fee_per_person
                    
        # Handle discount
        if bill.discount_amount > 0:
            if bill.discount_split_method == 'equal':
                discount_per_person = bill.discount_amount / num_participants
                for participant in participants:
                    participant.discount_amount = discount_per_person
                    
        return True
    
    def apply_custom_split(self, allocations):
        """Apply a custom split based on provided allocations
        
        Args:
            allocations: list of dicts with keys:
                - item_id: ID of the item
                - participant_id: ID of the participant
                - quantity: Quantity to allocate (optional)
                - amount: Amount to allocate (optional)
        """
        self.ensure_one()
        
        for allocation in allocations:
            self.allocate_item(
                allocation['item_id'],
                allocation['participant_id'],
                allocation.get('quantity'),
                allocation.get('amount')
            )
            
        return True

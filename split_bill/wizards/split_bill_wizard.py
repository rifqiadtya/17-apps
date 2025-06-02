# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SplitBillWizard(models.TransientModel):
    _name = 'split.bill.wizard'
    _description = 'Split Bill Wizard'

    bill_id = fields.Many2one('split.bill', string='Bill', required=True)
    
    # Related fields
    currency_id = fields.Many2one(related='bill_id.currency_id', string='Currency')
    company_id = fields.Many2one(related='bill_id.company_id', string='Company')
    total_amount = fields.Monetary(related='bill_id.total_amount', string='Total Amount')
    
    # Split method
    split_method = fields.Selection([
        ('equal', 'Split Equally'),
        ('amount', 'Split by Amount'),
        ('percentage', 'Split by Percentage'),
        ('item', 'Split by Items'),
        ('custom', 'Custom Split'),
    ], string='Split Method', required=True, default='equal')
    
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
    
    # Participants
    participant_ids = fields.One2many('split.bill.wizard.participant', 'wizard_id', 
                                      string='Participants')
    
    # Items
    item_ids = fields.One2many('split.bill.wizard.item', 'wizard_id', string='Items')
    
    @api.model
    def default_get(self, fields):
        res = super(SplitBillWizard, self).default_get(fields)
        
        if 'bill_id' in fields and not res.get('bill_id') and self._context.get('active_model') == 'split.bill':
            res['bill_id'] = self._context.get('active_id')
            
        if res.get('bill_id'):
            bill = self.env['split.bill'].browse(res['bill_id'])
            
            # Set split methods from bill
            if 'split_method' in fields:
                res['split_method'] = bill.split_method
            if 'delivery_fee_split_method' in fields:
                res['delivery_fee_split_method'] = bill.delivery_fee_split_method
            if 'discount_split_method' in fields:
                res['discount_split_method'] = bill.discount_split_method
                
            # Load existing participants
            if 'participant_ids' in fields:
                participants = []
                for participant in bill.participant_ids:
                    participants.append((0, 0, {
                        'partner_id': participant.partner_id.id,
                        'split_percentage': participant.split_percentage,
                        'amount_total': participant.amount_total,
                        'is_payer': participant.is_payer,
                    }))
                if participants:
                    res['participant_ids'] = participants
                    
            # Load existing items
            if 'item_ids' in fields:
                items = []
                for item in bill.item_ids:
                    items.append((0, 0, {
                        'item_id': item.id,
                        'name': item.name,
                        'quantity': item.quantity,
                        'price_unit': item.price_unit,
                        'price_subtotal': item.price_subtotal,
                        'price_total': item.price_total,
                        'participant_id': item.participant_id.id if item.participant_id else False,
                        'split_type': item.split_type,
                    }))
                if items:
                    res['item_ids'] = items
            
        return res
    
    @api.onchange('split_method')
    def _onchange_split_method(self):
        """Update bill's split method when changed in wizard"""
        if self.bill_id:
            self.bill_id.split_method = self.split_method
    
    @api.onchange('delivery_fee_split_method')
    def _onchange_delivery_fee_split_method(self):
        """Update bill's delivery fee split method when changed in wizard"""
        if self.bill_id:
            self.bill_id.delivery_fee_split_method = self.delivery_fee_split_method
    
    @api.onchange('discount_split_method')
    def _onchange_discount_split_method(self):
        """Update bill's discount split method when changed in wizard"""
        if self.bill_id:
            self.bill_id.discount_split_method = self.discount_split_method
    
    def action_add_participant(self):
        """Open wizard to add a participant"""
        self.ensure_one()
        return {
            'name': _('Add Participant'),
            'type': 'ir.actions.act_window',
            'res_model': 'split.bill.add.participant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_wizard_id': self.id},
        }
    
    def action_apply_split(self):
        """Apply the split configuration"""
        self.ensure_one()
        bill = self.bill_id
        
        # Update bill split methods
        bill.write({
            'split_method': self.split_method,
            'delivery_fee_split_method': self.delivery_fee_split_method,
            'discount_split_method': self.discount_split_method,
        })
        
        # Create or update participants
        for wizard_participant in self.participant_ids:
            bill_participant = bill.participant_ids.filtered(
                lambda p: p.partner_id == wizard_participant.partner_id
            )
            
            if bill_participant:
                # Update existing participant
                bill_participant.write({
                    'split_percentage': wizard_participant.split_percentage,
                    'is_payer': wizard_participant.is_payer,
                })
            else:
                # Create new participant
                self.env['split.bill.participant'].create({
                    'bill_id': bill.id,
                    'partner_id': wizard_participant.partner_id.id,
                    'split_percentage': wizard_participant.split_percentage,
                    'is_payer': wizard_participant.is_payer,
                })
        
        # Apply the split based on the selected method
        if self.split_method == 'equal':
            bill.apply_equal_split()
        elif self.split_method == 'item':
            # Update item assignments
            for wizard_item in self.item_ids:
                if wizard_item.item_id and wizard_item.participant_id:
                    wizard_item.item_id.participant_id = wizard_item.participant_id.id
            bill.apply_item_split()
        elif self.split_method == 'percentage':
            bill.apply_percentage_split()
        elif self.split_method == 'custom':
            bill.apply_custom_split()
        
        return {'type': 'ir.actions.act_window_close'}


class SplitBillWizardParticipant(models.TransientModel):
    _name = 'split.bill.wizard.participant'
    _description = 'Split Bill Wizard Participant'
    _rec_name = 'partner_id'

    wizard_id = fields.Many2one('split.bill.wizard', string='Wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Participant', required=True)
    
    # Split information
    split_percentage = fields.Float(string='Split Percentage', default=0.0)
    amount_total = fields.Monetary(string='Total Amount', default=0.0)
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Currency')
    is_payer = fields.Boolean(string='Is Payer', help='This participant paid the bill')
    
    @api.constrains('split_percentage')
    def _check_split_percentage(self):
        for participant in self:
            if participant.split_percentage < 0 or participant.split_percentage > 100:
                raise ValidationError(_('Split percentage must be between 0 and 100.'))


class SplitBillWizardItem(models.TransientModel):
    _name = 'split.bill.wizard.item'
    _description = 'Split Bill Wizard Item'

    wizard_id = fields.Many2one('split.bill.wizard', string='Wizard', required=True, ondelete='cascade')
    item_id = fields.Many2one('split.bill.item', string='Item')
    
    # Item information
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    price_subtotal = fields.Monetary(string='Subtotal')
    price_total = fields.Monetary(string='Total')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Currency')
    
    # Split information
    participant_id = fields.Many2one('split.bill.participant', string='Assigned To')
    split_type = fields.Selection([
        ('single', 'Single Participant'),
        ('multiple', 'Multiple Participants'),
        ('equal', 'Equal Split'),
        ('custom', 'Custom Split'),
    ], string='Split Type', default='single')
    
    # For multiple participant splits
    participant_ids = fields.Many2many('split.bill.participant', string='Participants')


class SplitBillAddParticipantWizard(models.TransientModel):
    _name = 'split.bill.add.participant.wizard'
    _description = 'Add Participant to Split Bill'

    wizard_id = fields.Many2one('split.bill.wizard', string='Split Bill Wizard')
    partner_id = fields.Many2one('res.partner', string='Participant', required=True)
    split_percentage = fields.Float(string='Split Percentage', default=0.0)
    is_payer = fields.Boolean(string='Is Payer')
    
    def action_add(self):
        """Add the participant to the split bill wizard"""
        self.ensure_one()
        
        if not self.wizard_id:
            return {'type': 'ir.actions.act_window_close'}
            
        # Create participant in wizard
        self.env['split.bill.wizard.participant'].create({
            'wizard_id': self.wizard_id.id,
            'partner_id': self.partner_id.id,
            'split_percentage': self.split_percentage,
            'is_payer': self.is_payer,
        })
        
        return {'type': 'ir.actions.act_window_close'}

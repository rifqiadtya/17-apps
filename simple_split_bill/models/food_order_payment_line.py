# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FoodOrderPaymentLine(models.Model):
    _name = 'food.order.payment.line'
    _description = 'Food Order Payment Line'
    _rec_name = 'partner_id'

    payment_id = fields.Many2one('food.order.payment', string='Payment', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Participant', required=True)
    
    # Related fields
    order_id = fields.Many2one('food.order', related='payment_id.order_id', store=True, string='Order')
    currency_id = fields.Many2one(related='payment_id.currency_id', string='Currency')
    
    # Amounts
    food_amount = fields.Monetary(string='Food Amount', default=0.0)
    fee_amount = fields.Monetary(string='Fee Amount', default=0.0)
    discount_amount = fields.Monetary(string='Discount Amount', default=0.0)
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
    
    # QR code for payment
    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True)
    
    @api.depends('food_amount', 'fee_amount', 'discount_amount')
    def _compute_total_amount(self):
        for line in self:
            line.total_amount = line.food_amount + line.fee_amount - line.discount_amount
    
    @api.depends('partner_id', 'total_amount', 'order_id.access_token')
    def _compute_qr_code(self):
        for line in self:
            if line.partner_id and line.total_amount > 0 and line.order_id.access_token:
                try:
                    import qrcode
                    import base64
                    from io import BytesIO
                    
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    url = f"{base_url}/food/receipt/{line.order_id.id}/{line.order_id.access_token}?partner_id={line.partner_id.id}"
                    
                    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                    qr.add_data(url)
                    qr.make(fit=True)
                    img = qr.make_image()
                    
                    buffered = BytesIO()
                    img.save(buffered, format="PNG")
                    line.qr_code = base64.b64encode(buffered.getvalue())
                except ImportError:
                    line.qr_code = False
            else:
                line.qr_code = False
    
    def action_mark_as_paid(self):
        """Mark payment line as paid"""
        for line in self:
            line.write({
                'is_paid': True,
                'payment_date': fields.Date.context_today(self),
            })
            
            # Check if all lines are paid and update the main payment
            if all(line.is_paid for line in line.payment_id.payment_line_ids):
                line.payment_id.is_paid = True
                
        return True
    
    def action_mark_as_unpaid(self):
        """Mark payment line as unpaid"""
        for line in self:
            line.write({
                'is_paid': False,
                'payment_date': False,
            })
            
            # Update the main payment
            line.payment_id.is_paid = False
                
        return True
    
    def action_view_items(self):
        """View items assigned to this participant"""
        self.ensure_one()
        return {
            'name': _('Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'food.order.line',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id), ('order_id', '=', self.order_id.id)],
            'context': {'default_partner_id': self.partner_id.id, 'default_order_id': self.order_id.id},
        }

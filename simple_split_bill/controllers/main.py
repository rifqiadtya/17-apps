# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from werkzeug.exceptions import NotFound


class FoodOrderController(http.Controller):
    
    @http.route(['/food/receipt/<int:order_id>/<string:access_token>'], type='http', auth="public", website=True)
    def food_receipt(self, order_id, access_token, partner_id=None, **kw):
        """Display the food order receipt for public access"""
        try:
            order_sudo = self._document_check_access('food.order', order_id, access_token)
        except (AccessError, ValidationError):
            return request.redirect('/web/login?redirect=/food/receipt/%s/%s' % (order_id, access_token))
        
        values = {
            'order': order_sudo,
            'partner_id': int(partner_id) if partner_id else None,
        }
        
        # If partner_id is provided, filter the view to show only that partner's items
        if partner_id:
            partner = request.env['res.partner'].sudo().browse(int(partner_id))
            if not partner.exists() or partner not in order_sudo.participant_ids:
                partner_id = None
            else:
                values['partner'] = partner
                
                # Get payment line for this partner
                if order_sudo.payment_id:
                    payment_line = order_sudo.payment_id.payment_line_ids.filtered(lambda l: l.partner_id.id == int(partner_id))
                    if payment_line:
                        values['payment_line'] = payment_line
                
                # Get items for this partner
                items = order_sudo.line_ids.filtered(lambda l: l.partner_id.id == int(partner_id))
                values['items'] = items
        
        return request.render('simple_split_bill.food_receipt_template', values)
    
    @http.route(['/food/receipt/<int:order_id>/<string:access_token>/mark_paid'], type='http', auth="public", website=True)
    def mark_payment_paid(self, order_id, access_token, partner_id=None, **kw):
        """Mark a payment as paid from the public receipt"""
        try:
            order_sudo = self._document_check_access('food.order', order_id, access_token)
        except (AccessError, ValidationError):
            return request.redirect('/web/login?redirect=/food/receipt/%s/%s' % (order_id, access_token))
        
        if partner_id and order_sudo.payment_id:
            payment_line = order_sudo.payment_id.payment_line_ids.filtered(lambda l: l.partner_id.id == int(partner_id))
            if payment_line:
                payment_line.action_mark_as_paid()
        
        return request.redirect('/food/receipt/%s/%s?partner_id=%s' % (order_id, access_token, partner_id))
    
    def _document_check_access(self, model_name, document_id, access_token=None):
        """Check if the user has access to the document"""
        document = request.env[model_name].sudo().browse(document_id)
        if not document.exists():
            raise NotFound()
        
        if access_token and document.check_access_token(access_token):
            return document
        
        # If no token or invalid token, check regular access rights
        document = request.env[model_name].browse(document_id)
        document.check_access_rights('read')
        document.check_access_rule('read')
        return document

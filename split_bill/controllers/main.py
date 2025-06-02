# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json


class SplitBillController(http.Controller):
    @http.route('/split_bill/share/<int:bill_id>', type='http', auth='public', website=True)
    def split_bill_share(self, bill_id, access_token=None, **kw):
        """Public page to share a split bill with participants"""
        bill = request.env['split.bill'].sudo().browse(bill_id)
        
        if not bill.exists():
            return request.render('split_bill.split_bill_not_found')
        
        # TODO: Implement access token validation for security
        
        values = {
            'bill': bill,
            'participants': bill.participant_ids,
            'items': bill.item_ids,
        }
        
        return request.render('split_bill.split_bill_share_template', values)
    
    @http.route('/split_bill/payment/<int:participant_id>', type='http', auth='public', website=True)
    def split_bill_payment(self, participant_id, access_token=None, **kw):
        """Public payment page for a participant"""
        participant = request.env['split.bill.participant'].sudo().browse(participant_id)
        
        if not participant.exists():
            return request.render('split_bill.participant_not_found')
        
        # TODO: Implement access token validation for security
        
        values = {
            'participant': participant,
            'bill': participant.bill_id,
            'items': participant.item_ids,
        }
        
        return request.render('split_bill.split_bill_payment_template', values)
    
    @http.route('/split_bill/api/bill/<int:bill_id>', type='json', auth='user')
    def get_bill_data(self, bill_id):
        """API endpoint to get bill data"""
        bill = request.env['split.bill'].browse(bill_id)
        
        if not bill.exists():
            return {'error': 'Bill not found'}
        
        # Check access rights
        try:
            bill.check_access_rights('read')
            bill.check_access_rule('read')
        except Exception:
            return {'error': 'Access denied'}
        
        # Prepare bill data
        participants = []
        for participant in bill.participant_ids:
            participants.append({
                'id': participant.id,
                'name': participant.partner_id.name,
                'amount_total': participant.amount_total,
                'amount_paid': participant.amount_paid,
                'amount_due': participant.amount_due,
                'payment_status': participant.payment_status,
            })
        
        items = []
        for item in bill.item_ids:
            items.append({
                'id': item.id,
                'name': item.name,
                'quantity': item.quantity,
                'price_unit': item.price_unit,
                'price_subtotal': item.price_subtotal,
                'price_total': item.price_total,
                'participant_id': item.participant_id.id if item.participant_id else False,
                'is_split': item.is_split,
                'split_type': item.split_type,
            })
        
        return {
            'id': bill.id,
            'name': bill.name,
            'date': bill.date,
            'total_amount': bill.total_amount,
            'subtotal_amount': bill.subtotal_amount,
            'tax_amount': bill.tax_amount,
            'discount_amount': bill.discount_amount,
            'delivery_fee': bill.delivery_fee,
            'state': bill.state,
            'participants': participants,
            'items': items,
        }
    
    @http.route('/split_bill/api/split_item', type='json', auth='user')
    def split_item(self, item_id, split_type, participant_data):
        """API endpoint to split an item"""
        item = request.env['split.bill.item'].browse(item_id)
        
        if not item.exists():
            return {'error': 'Item not found'}
        
        # Check access rights
        try:
            item.check_access_rights('write')
            item.check_access_rule('write')
        except Exception:
            return {'error': 'Access denied'}
        
        try:
            if split_type == 'single':
                # Assign to a single participant
                participant_id = participant_data.get('participant_id')
                if not participant_id:
                    return {'error': 'Participant ID required'}
                
                result = item.assign_to_participant(participant_id)
                if not result:
                    return {'error': 'Failed to assign item'}
                    
            elif split_type == 'equal':
                # Split equally among participants
                participant_ids = participant_data.get('participant_ids', [])
                if not participant_ids:
                    return {'error': 'Participant IDs required'}
                
                result = item.split_equally(participant_ids)
                if not result:
                    return {'error': 'Failed to split item'}
                    
            elif split_type == 'custom':
                # Custom split
                allocations = participant_data.get('allocations', [])
                if not allocations:
                    return {'error': 'Allocations required'}
                
                result = item.split_custom(allocations)
                if not result:
                    return {'error': 'Failed to split item'}
                    
            else:
                return {'error': 'Invalid split type'}
                
            return {'success': True}
            
        except Exception as e:
            return {'error': str(e)}
    
    @http.route('/split_bill/api/register_payment', type='json', auth='user')
    def register_payment(self, participant_id, amount, payment_method, payment_reference=None, note=None):
        """API endpoint to register a payment"""
        participant = request.env['split.bill.participant'].browse(participant_id)
        
        if not participant.exists():
            return {'error': 'Participant not found'}
        
        # Check access rights
        try:
            participant.check_access_rights('write')
            participant.check_access_rule('write')
        except Exception:
            return {'error': 'Access denied'}
        
        try:
            payment = request.env['split.bill.payment'].create({
                'participant_id': participant_id,
                'amount': amount,
                'payment_method': payment_method,
                'payment_reference': payment_reference,
                'note': note,
            })
            
            payment.action_confirm()
            
            return {
                'success': True,
                'payment_id': payment.id,
                'new_amount_paid': participant.amount_paid,
                'new_amount_due': participant.amount_due,
                'new_payment_status': participant.payment_status,
            }
            
        except Exception as e:
            return {'error': str(e)}

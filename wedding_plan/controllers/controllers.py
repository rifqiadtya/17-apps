# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.http_routing.models.ir_http import slug
from odoo.http import request

class WeddingInvitation(http.Controller):

    @http.route('''/invitation/<model("res.partner"):record>''', type='http', auth="public", website=True)
    def invitation_link(self, record, **kw):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        wishes = request.env['wedding.wishes'].search([])
        return request.render("wedding_plan.invitation_link_template", {'record': record, 'base_url': base_url, 'wishes': wishes})

    @http.route('/send-wish', type='json', auth='public')
    def send_wish(self, context=None, **kw):
        request.env['wedding.wishes'].sudo().create(kw)
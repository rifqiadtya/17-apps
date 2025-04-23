from odoo import _, api, fields, models
import re
from odoo.tools.safe_eval import safe_eval, time

# Api key whatsapp
# KaX06yufKGkNuz7d2j3IiTgoEClx43N7LL3N

class SendingWeddingInvitation(models.TransientModel):
    _name = 'sending.wedding.invitation'
    _description = 'Sending Wedding Invitation'
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    template_id = fields.Many2one('wedding.invitation.template', string='Template')
    content = fields.Html('')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        def _getattrstring(self, obj, field_str):
            field_str = field_str.replace('$', obj)
            try:
                return eval(field_str)
            except Exception as e:
                return "*** Error: %s" % e

        self.content = self.template_id.content
        if self.content:
            pattern = r'\$\.[-\w\.]+'
            formatted_string = re.findall(pattern, self.content)

            for formatted in formatted_string:
                self.content = self.content.replace(formatted, _getattrstring(self, 'self.partner_id', formatted))

    
    def action_send(self):
        self.partner_id.template_id = self.template_id.id
        self.partner_id.invitation_sent = True

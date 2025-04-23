from odoo import _, api, fields, models
from odoo.addons.http_routing.models.ir_http import slug
class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_wedding_invitation = fields.Boolean('Is Wedding Invitation')    
    quantity = fields.Integer('Quantity')
    invitation_sent = fields.Boolean('Invitation Sent')    
    invitation_link = fields.Char(compute='_compute_invitation_link', string='Invitation Link')
    wedding_session_id = fields.Many2one('wedding.session', string='Wedding Session', default=lambda self: self.env['wedding.session'].search([], limit=1))
    template_id = fields.Many2one('wedding.invitation.template', string='Template')

    def action_send(self):
        self.ensure_one()
        return {
            'name': _('Send Link'),
            'view_mode': 'form',
            'res_model': 'sending.wedding.invitation',
            'type': 'ir.actions.act_window',
            'context': {'default_partner_id': self.id, 'default_template_id': self.template_id.id},
            'target': 'new',
        }

    def _compute_invitation_link(self):
        for rec in self:
            rec.invitation_link = self.env['ir.config_parameter'].sudo().get_param('web.base.url') + "/invitation/" + slug(rec)

class WeddingInvitationTemplate(models.Model):
    _name = 'wedding.invitation.template'
    _description = 'Wedding Invitation Template'
    
    name = fields.Char('')
    content = fields.Html('')
from odoo import _, models


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    def action_open_invite_by_tag_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invite Participants by Tag'),
            'res_model': 'course.invite.by.tag.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_course_id': self.id,
            },
        }

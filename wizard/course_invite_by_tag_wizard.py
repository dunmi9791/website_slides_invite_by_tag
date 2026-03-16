from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class CourseInviteByTagWizard(models.TransientModel):
    _name = 'course.invite.by.tag.wizard'
    _description = 'Invite Course Participants by Tag'

    course_id = fields.Many2one('slide.channel', string='Course', required=True, readonly=True)
    tag_ids = fields.Many2many('res.partner.category', string='Partner Tags', required=True)
    tag_match = fields.Selection(
        [('any', 'Match Any Tag'), ('all', 'Match All Tags')],
        string='Tag Match Rule',
        default='any',
        required=True,
    )
    only_with_email = fields.Boolean(
        string='Only Contacts With Email',
        default=True,
        help='Keep only contacts that have an email address.',
    )
    exclude_already_enrolled = fields.Boolean(
        string='Exclude Already Enrolled',
        default=True,
        help='Skip contacts that are already enrolled in the selected course.',
    )
    auto_enroll = fields.Boolean(
        string='Enroll Participants',
        default=True,
        help='Create the participant records immediately for the matched contacts.',
    )
    send_email = fields.Boolean(
        string='Send Email Notification',
        default=True,
        help='Send an email to matched contacts with the course link.',
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'course_invite_by_tag_partner_rel',
        'wizard_id',
        'partner_id',
        string='Matched Participants',
        compute='_compute_partner_ids',
    )
    matched_count = fields.Integer(string='Matched Count', compute='_compute_partner_ids')
    enrolled_count = fields.Integer(string='To Enroll', compute='_compute_result_counts')
    email_count = fields.Integer(string='To Email', compute='_compute_result_counts')

    @api.depends('partner_ids', 'auto_enroll', 'send_email')
    def _compute_result_counts(self):
        for wizard in self:
            wizard.enrolled_count = len(wizard.partner_ids) if wizard.auto_enroll else 0
            if wizard.send_email:
                wizard.email_count = len(wizard.partner_ids.filtered(lambda p: p.email))
            else:
                wizard.email_count = 0

    @api.depends(
        'course_id',
        'tag_ids',
        'tag_match',
        'only_with_email',
        'exclude_already_enrolled',
    )
    def _compute_partner_ids(self):
        Partner = self.env['res.partner']
        for wizard in self:
            partners = Partner.browse()
            if wizard.course_id and wizard.tag_ids:
                partners = wizard._get_matching_partners()
            wizard.partner_ids = partners
            wizard.matched_count = len(partners)

    def _get_matching_partners(self):
        self.ensure_one()
        Partner = self.env['res.partner']

        domain = [('active', '=', True), ('type', '!=', 'private')]
        if self.only_with_email:
            domain.append(('email', '!=', False))

        if self.tag_match == 'any':
            domain.append(('category_id', 'in', self.tag_ids.ids))
            partners = Partner.search(domain)
        else:
            partners = Partner.search(domain)
            partners = partners.filtered(lambda p: all(tag in p.category_id for tag in self.tag_ids))

        if self.exclude_already_enrolled and self.course_id:
            enrolled_partner_ids = set(self.course_id.channel_partner_ids.mapped('partner_id').ids)
            partners = partners.filtered(lambda p: p.id not in enrolled_partner_ids)

        return partners.sorted(lambda p: (p.name or '').lower())

    def _prepare_enrollment_values(self, partner):
        self.ensure_one()
        return {
            'channel_id': self.course_id.id,
            'partner_id': partner.id,
            'member_status': 'joined',
            'completion': 0,
        }

    def _ensure_enrollments(self):
        self.ensure_one()
        ChannelPartner = self.env['slide.channel.partner']
        existing = ChannelPartner.search([
            ('channel_id', '=', self.course_id.id),
            ('partner_id', 'in', self.partner_ids.ids),
        ])
        existing_partner_ids = set(existing.mapped('partner_id').ids)

        to_create_vals = [
            self._prepare_enrollment_values(partner)
            for partner in self.partner_ids
            if partner.id not in existing_partner_ids
        ]
        if to_create_vals:
            ChannelPartner.create(to_create_vals)
        return len(to_create_vals)

    def _get_course_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        website_path = self.course_id.website_url or ''
        if website_path and website_path.startswith('http'):
            return website_path
        return '%s%s' % (base_url.rstrip('/'), website_path)

    def _send_notifications(self):
        self.ensure_one()
        template = self.env.ref(
            'website_slides_invite_by_tag.mail_template_course_invite_by_tag',
            raise_if_not_found=False,
        )
        if not template:
            return 0

        recipients = self.partner_ids.filtered(lambda p: p.email)
        if not recipients:
            return 0

        course_url = self._get_course_url()
        count = 0
        for partner in recipients:
            template.with_context(
                invite_course_name=self.course_id.name,
                invite_course_url=course_url,
            ).send_mail(partner.id, force_send=True)
            count += 1
        return count

    def action_invite_participants(self):
        self.ensure_one()

        if not self.tag_ids:
            raise UserError(_('Please select at least one tag.'))

        if not self.partner_ids:
            raise UserError(_('No participants matched the selected tags and filters.'))

        if not self.auto_enroll and not self.send_email:
            raise UserError(_('Enable at least one action: enroll participants or send email notification.'))

        enrolled = 0
        emailed = 0

        if self.auto_enroll:
            enrolled = self._ensure_enrollments()

        if self.send_email:
            emailed = self._send_notifications()

        message_parts = []
        if self.auto_enroll:
            message_parts.append(_('Enrolled %(count)s participant(s).', count=enrolled))
        if self.send_email:
            message_parts.append(_('Sent %(count)s email notification(s).', count=emailed))

        self.course_id.message_post(body=' '.join(message_parts))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invite by Tag Completed'),
                'message': ' '.join(message_parts),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

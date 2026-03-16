from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CourseInviteByTagWizard(models.TransientModel):
    _name = 'course.invite.by.tag.wizard'
    _description = 'Invite Course Participants by Tag'

    course_id = fields.Many2one(
        'slide.channel',
        string='Course',
        required=True,
        readonly=True,
    )

    partner_tag_ids = fields.Many2many(
        'res.partner.category',
        'course_invite_partner_tag_rel',
        'wizard_id',
        'tag_id',
        string='Partner Tags',
    )

    employee_tag_ids = fields.Many2many(
        'hr.employee.category',
        'course_invite_employee_tag_rel',
        'wizard_id',
        'tag_id',
        string='Employee Tags',
    )

    tag_match = fields.Selection(
        [('any', 'Match Any Tag'), ('all', 'Match All Tags')],
        string='Tag Match Rule',
        default='any',
        required=True,
        help='Applies independently to partner tags and employee tags.',
    )

    only_with_email = fields.Boolean(
        string='Only Participants With Email',
        default=True,
        help='Keep only participants that have an email address.',
    )

    exclude_already_enrolled = fields.Boolean(
        string='Exclude Already Enrolled',
        default=True,
        help='Skip participants that are already enrolled in the selected course.',
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

    employee_ids = fields.Many2many(
        'hr.employee',
        'course_invite_employee_rel',
        'wizard_id',
        'employee_id',
        string='Matched Employees',
        compute='_compute_matches',
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'course_invite_by_tag_partner_rel',
        'wizard_id',
        'partner_id',
        string='Matched Participants',
        compute='_compute_matches',
    )

    matched_employee_count = fields.Integer(
        string='Matched Employees',
        compute='_compute_matches',
    )

    matched_count = fields.Integer(
        string='Matched Participants',
        compute='_compute_matches',
    )

    enrolled_count = fields.Integer(
        string='To Enroll',
        compute='_compute_result_counts',
    )

    email_count = fields.Integer(
        string='To Email',
        compute='_compute_result_counts',
    )

    unresolved_employee_count = fields.Integer(
        string='Employees Without Linked User/Partner',
        compute='_compute_matches',
        help='Employees matched by employee tags but without a linked user partner, so they cannot be enrolled directly.',
    )

    @api.depends('partner_ids', 'auto_enroll', 'send_email')
    def _compute_result_counts(self):
        for wizard in self:
            wizard.enrolled_count = len(wizard.partner_ids) if wizard.auto_enroll else 0
            wizard.email_count = len(wizard.partner_ids.filtered(lambda p: p.email)) if wizard.send_email else 0

    @api.depends(
        'course_id',
        'partner_tag_ids',
        'employee_tag_ids',
        'tag_match',
        'only_with_email',
        'exclude_already_enrolled',
    )
    def _compute_matches(self):
        for wizard in self:
            employees, partners, unresolved_count = wizard._collect_matches()

            wizard.employee_ids = employees
            wizard.partner_ids = partners
            wizard.matched_employee_count = len(employees)
            wizard.matched_count = len(partners)
            wizard.unresolved_employee_count = unresolved_count

    def _collect_matches(self):
        self.ensure_one()

        Employee = self.env['hr.employee']
        Partner = self.env['res.partner']

        employees = Employee.browse()
        partners = Partner.browse()
        unresolved_employee_count = 0

        # -----------------------------
        # Match partners from partner tags
        # -----------------------------
        if self.partner_tag_ids:
            partner_domain = [('active', '=', True), ('type', '!=', 'private')]

            if self.only_with_email:
                partner_domain.append(('email', '!=', False))

            if self.tag_match == 'any':
                partner_domain.append(('category_id', 'in', self.partner_tag_ids.ids))
                partner_matches = Partner.search(partner_domain)
            else:
                candidate_partners = Partner.search(partner_domain)
                selected_partner_tag_ids = set(self.partner_tag_ids.ids)
                partner_matches = candidate_partners.filtered(
                    lambda p: selected_partner_tag_ids.issubset(set(p.category_id.ids))
                )

            partners |= partner_matches

        # -----------------------------
        # Match employees from employee tags
        # -----------------------------
        if self.employee_tag_ids:
            employee_domain = [('active', '=', True)]

            if self.tag_match == 'any':
                employee_domain.append(('category_ids', 'in', self.employee_tag_ids.ids))
                employee_matches = Employee.search(employee_domain)
            else:
                candidate_employees = Employee.search(employee_domain)
                selected_employee_tag_ids = set(self.employee_tag_ids.ids)
                employee_matches = candidate_employees.filtered(
                    lambda e: selected_employee_tag_ids.issubset(set(e.category_ids.ids))
                )

            employees |= employee_matches

            for employee in employee_matches:
                partner = employee.user_id.partner_id if employee.user_id and employee.user_id.partner_id else False
                if partner:
                    if not self.only_with_email or partner.email:
                        partners |= partner
                else:
                    unresolved_employee_count += 1

        # -----------------------------
        # Exclude already enrolled
        # -----------------------------
        if self.exclude_already_enrolled and self.course_id and partners:
            enrolled_partner_ids = set(self.course_id.channel_partner_ids.mapped('partner_id').ids)
            partners = partners.filtered(lambda p: p.id not in enrolled_partner_ids)

        employees = employees.sorted(lambda e: (e.name or '').lower())
        partners = partners.sorted(lambda p: (p.name or '').lower())

        return employees, partners, unresolved_employee_count

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

        if not self.partner_tag_ids and not self.employee_tag_ids:
            raise UserError(_('Please select at least one partner tag or employee tag.'))

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
        if self.partner_tag_ids:
            message_parts.append(_('Partner tags used: %(tags)s.', tags=', '.join(self.partner_tag_ids.mapped('name'))))
        if self.employee_tag_ids:
            message_parts.append(_('Employee tags used: %(tags)s.', tags=', '.join(self.employee_tag_ids.mapped('name'))))
        if self.auto_enroll:
            message_parts.append(_('Enrolled %(count)s participant(s).', count=enrolled))
        if self.send_email:
            message_parts.append(_('Sent %(count)s email notification(s).', count=emailed))
        if self.unresolved_employee_count:
            message_parts.append(_('%(count)s employee(s) had no linked user/partner and were skipped for enrollment.', count=self.unresolved_employee_count))

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
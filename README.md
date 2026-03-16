# eLearning Invite by Tag

This module adds an **Invite by Tag** action to Odoo eLearning courses.

## What it does

- Select one or more partner tags from the course form
- Match contacts with **any** selected tag or **all** selected tags
- Preview matched participants
- Optionally exclude already enrolled contacts
- Optionally enroll matched contacts immediately
- Optionally send email notifications with the course link

## Dependencies

- `website_slides`
- `contacts`
- `mail`

## Notes

- This module works with `res.partner` tags (`res.partner.category`)
- Course membership is created in `slide.channel.partner`
- Email notifications are sent only to contacts that have an email address
- The button is visible to eLearning managers

## Typical usage

1. Open a course
2. Click **Invite by Tag**
3. Select tags and filters
4. Run the invite
# website_slides_invite_by_tag

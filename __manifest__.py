{
    'name': 'eLearning Invite by Tag',
    'version': '18.0.1.1.0',
    'summary': 'Invite and enroll eLearning participants by employee tags and partner tags',
    'description': '''
Bulk invite or enroll eLearning course participants from:
- Partner Tags
- Employee Tags

Features:
- Invite from course form using partner tags and/or employee tags
- Match any selected tag or all selected tags
- Preview matched employees and participants before execution
- Exclude already enrolled participants
- Optional direct enrollment
- Optional email notification with course link
''',
    'category': 'Website/eLearning',
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'depends': ['website_slides', 'contacts', 'mail', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'views/slide_channel_views.xml',
        'views/course_invite_by_tag_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
# -*- coding: utf-8 -*-
import requests


class Mailgun(object):

    """Interface to Mailgun email API."""

    def __init__(self, app=None):
        super(Mailgun, self).__init__()

        self.MAILGUN_API_KEY = None
        self.MAILGUN_DOMAIN_NAME = None
        self.MAILGUN_DEFAULT_SENDER = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app object."""
        self.MAILGUN_API_KEY = app.config['MAILGUN_API_KEY']
        self.MAILGUN_DOMAIN_NAME = app.config['MAILGUN_DOMAIN_NAME']
        self.MAILGUN_SENDER_NAME = app.config.get('MAILGUN_SENDER_NAME', 'Mailgun User')

    def send(self, to_addr, subject, text):
        """Send email."""
        url = "https://api.mailgun.net/v3/{}/messages".format(self.MAILGUN_DOMAIN_NAME)
        auth = ('api', self.MAILGUN_API_KEY)
        data = {
            'from': "{} <mailgun@{}>".format(self.MAILGUN_SENDER_NAME, self.MAILGUN_DOMAIN_NAME),
            'to': to_addr,
            'subject': subject,
            'text': text,
        }
        response = requests.post(url, auth=auth, data=data)
        response.raise_for_status()
        return response

    def submit_to_lims(self, ticket_id):
        """Update ticket to mark samples added to LIMS."""
        to_addr = 'supportsystem@clinicalgenomics.se'
        subject = "[#{}] Added to LIMS".format(ticket_id)
        text = """Samples added to LIMS.

        /
        Your friendly Clinicl Genomics Bot
        """
        self.send(to_addr, subject, text)

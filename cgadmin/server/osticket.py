# -*- coding: utf-8 -*-
import os.path
import requests


class TicketCreationError(Exception):
    pass


class OsTicket(object):

    def __init__(self):
        self.headers = None
        self.url = None

    def init_app(self, app):
        """Initialize the API."""
        self.headers = {'X-API-Key': app.config['OSTICKET_API_KEY']}
        self.url = os.path.join(app.config['OSTICKET_DOMAIN'], 'api/tickets.json')

    def open_ticket(self, name, email, subject, message):
        """Open a new ticket through the REST API."""
        data = dict(name=name, email=email, subject=subject, message=message)
        res = requests.post(self.url, json=data, headers=self.headers)
        if res.ok:
            return res.text
        else:
            raise TicketCreationError(res)

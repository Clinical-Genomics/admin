# -*- coding: utf-8 -*-
from sqlservice import SQLClient

from .models import Model


def connect(db_uri):
    """Connect to database."""
    db = SQLClient({'SQL_DATABASE_URI': db_uri}, model_class=Model)
    return db


def connect_app(app):
    """Connect Flask application."""
    db = connect(app.config['SQL_DATABASE_URI'])
    return db

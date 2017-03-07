# -*- coding: utf-8 -*-
from sqlservice import SQLClient

from .models import Model, ApplicationTagVersion, ApplicationTag


def connect(db_uri):
    """Connect to database."""
    db = SQLClient({'SQL_DATABASE_URI': db_uri}, model_class=Model)
    return db


def connect_app(app):
    """Connect Flask application."""
    db = connect(app.config['SQL_DATABASE_URI'])
    return db


def latest_version(db, apptag_id):
    """Get the latest version of an application tag."""
    version = (db.ApplicationTagVersion.join(ApplicationTagVersion.apptag)
                 .filter(ApplicationTag.name == apptag_id)
                 .order_by(ApplicationTagVersion.valid_from.desc())
                 .first())
    return version

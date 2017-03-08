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


def parse_db_project(new_project):
    """Parse Project from database to JSON."""
    project_data = {
        'name': new_project.name,
        'customer': new_project.customer.customer_id,
        'families': [],
    }
    for family in new_project.families:
        family_data = {
            'name': family.name,
            'panels': family.panels,
            'priority': family.priority,
            'delivery_type': family.delivery_type,
            'require_qcok': family.require_qcok,
            'samples': [],
        }
        for sample in family.samples:
            sample_data = {
                'name': sample.name,
                'sex': sample.sex,
                'status': sample.status,
                'application_tag': sample.application_tag.name,
                'capture_kit': sample.capture_kit,
                'source': sample.source,
                'container': sample.container,
                'container_name': sample.container_name,
                'well_position': sample.well_position,
                'quantity': sample.quantity,
            }
            for parent_id in ('father', 'mother'):
                parent_sample = getattr(sample, parent_id)
                if parent_sample:
                    sample_data[parent_id] = parent_sample.name
            family_data['samples'].append(sample_data)
        project_data['families'].append(family_data)

    return project_data

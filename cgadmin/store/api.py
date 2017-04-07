# -*- coding: utf-8 -*-
from sqlservice import SQLClient

from .models import Model, ApplicationTagVersion, ApplicationTag
from cgadmin.schema import schema_project


class AdminDatabase(SQLClient):
    """docstring for AdminDatabase"""
    def __init__(self, db_uri):
        super(AdminDatabase, self).__init__({'SQL_DATABASE_URI': db_uri}, model_class=Model)

    def latest_version(self, apptag_id):
        """Get the latest version of an application tag."""
        version = (self.ApplicationTagVersion
                       .join(ApplicationTagVersion.apptag)
                       .filter(ApplicationTag.name == apptag_id)
                       .order_by(ApplicationTagVersion.valid_from.desc())
                       .first())
        return version

    def full_schema(self):
        """Fill out schema with all possible values."""
        schema_project['properties']['customer'] = {
            "enum": [customer.customer_id for customer in self.Customer]
        }
        schema_project['properties']['families']['items']['properties']['samples']['items']['properties']['application_tag'] = {
            "enum": [apptag.name for apptag in self.ApplicationTag]
        }
        return schema_project

    def invoice(self, invoice_id):
        """Fetch invoice record from the database."""
        invoice_obj = self.Invoice.filter_by(invoice_id=invoice_id).first()
        return invoice_obj

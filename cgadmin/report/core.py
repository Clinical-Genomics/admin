# -*- coding: utf-8 -*-
import logging

from datetime import datetime
import json

from dateutil import parser
import click
from jinja2 import Environment, PackageLoader, select_autoescape

from cgadmin.store.models import ApplicationTag, ApplicationTagVersion

log = logging.getLogger(__name__)


@click.command()
@click.argument('in_data', type=click.File('r'), default='-')
@click.pass_context
def report(context, in_data):
    """Generate a QC report for a case."""
    admin_db = context.obj['db']
    case_data = json.load(in_data)
    template_out = export_report(admin_db, case_data)
    click.echo(template_out)


def export_report(admin_db, case_data):
    """Generate a delivery report."""
    case_data['today'] = datetime.today()
    case_data['customer'] = admin_db.Customer.filter_by(customer_id=case_data['customer']).first()

    apptag_ids = set()
    for sample in case_data['samples']:
        apptag_ids.add((sample['app_tag'], sample['app_tag_version']))
        method_types = ['library_prep_method', 'sequencing_method', 'delivery_method']
        for method_type in method_types:
            document_raw = sample.get(method_type)
            if document_raw is None:
                continue
            doc_no, doc_version = [int(part) for part in document_raw.split(':')]
            method = admin_db.Method.filter_by(document=doc_no).first()
            if method is None or method.document_version != doc_version:
                log.warn("method not found in admin db: %s", document_raw)
            sample[method_type] = method
            sample['project'] = sample['project'].split()[0]

        # parse dates into datetime objects
        date_keys = set(['received_at', 'delivery_date'])
        for date_key in date_keys:
            if date_key in sample:
                if not isinstance(sample[date_key], datetime):
                    sample[date_key] = parser.parse(sample[date_key])
        if all(date_key in sample for date_key in date_keys):
            processing_time = sample['delivery_date'] - sample['received_at']
            sample['processing_time'] = processing_time.days

    versions = []
    for apptag_id, apptag_version in apptag_ids:
        version = (admin_db.ApplicationTagVersion.join(ApplicationTagVersion.apptag)
                           .filter(ApplicationTag.name == apptag_id,
                                   ApplicationTagVersion.version == apptag_version)
                           .first())
        if version:
            versions.append(version)
    is_accredited = all(version.is_accredited for version in versions)
    case_data['apptags'] = versions
    case_data['accredited'] = is_accredited

    env = Environment(
        loader=PackageLoader('cgadmin', 'report/templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template('report.html')
    template_out = template.render(**case_data)

    return template_out

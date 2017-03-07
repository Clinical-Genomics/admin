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
    data = json.load(in_data)
    db = context.obj['db']
    data['today'] = datetime.today()
    data['customer'] = db.Customer.filter_by(customer_id=data['customer']).first()

    apptag_ids = set()
    for sample in data['samples']:
        apptag_ids.add((sample['app_tag'], sample['app_tag_version']))
        method_types = ['library_prep_method', 'sequencing_method', 'delivery_method']
        for method_type in method_types:
            document_raw = sample.get(method_type)
            if document_raw is None:
                continue
            doc_no, doc_version = [int(part) for part in document_raw.split(':')]
            method = db.Method.filter_by(document=doc_no).first()
            if method is None:
                log.warn("method not found in admin db: %s", document_raw)
            elif method.version != doc_version:
                log.warn("method version not the same as in database")
                method.version = doc_version
            sample[method_type] = method
            sample['project'] = sample['project'].split()[0]

        # parse dates into datetime objects
        date_keys = set(['received_at', 'delivery_date'])
        for date_key in date_keys:
            if date_key in sample:
                sample[date_key] = parser.parse(sample[date_key])
        if all(date_key in sample for date_key in date_keys):
            processing_time = sample['delivery_date'] - sample['received_at']
            sample['processing_time'] = processing_time.days

    versions = []
    for apptag_id, apptag_version in apptag_ids:
        version = (db.ApplicationTagVersion.join(ApplicationTagVersion.apptag)
                     .filter(ApplicationTag.name == apptag_id,
                             ApplicationTagVersion.version == apptag_version)
                     .first())
        if version:
            versions.append(version)
    is_accredited = all(version.is_accredited for version in versions)
    data['apptags'] = versions
    data['accredited'] = is_accredited

    env = Environment(
        loader=PackageLoader('cgadmin', 'report/templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template('report.html')
    template_out = template.render(**data)

    click.echo(template_out)

# -*- coding: utf-8 -*-
from datetime import datetime
import json

from dateutil import parser
import click
from jinja2 import Environment, PackageLoader, select_autoescape

from cgadmin.store.models import ApplicationTag, ApplicationTagVersion


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
        method_types = ['library_prep_method', 'sequencing_method']
        for method_type in method_types:
            document_raw = sample.get(method_type)
            if document_raw is None:
                continue
            doc_no, doc_version = [int(part) for part in document_raw.split(':')]
            method = db.Method.filter_by(document=doc_no,
                                         document_version=doc_version).first()
            sample[method_type] = method

    apptags = []
    for apptag_id, apptag_version in apptag_ids:
        apptag = (db.ApplicationTagVersion.join(ApplicationTagVersion.apptag)
                    .filter(ApplicationTag.name == apptag_id,
                            ApplicationTagVersion.version == apptag_version)
                    .first())
        if apptag:
            apptags.append(apptag)
    data['apptags'] = apptags

    env = Environment(
        loader=PackageLoader('cgadmin', 'report/templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    env.filters['date'] = parser.parse
    template = env.get_template('report.html')
    template_out = template.render(**data)

    click.echo(template_out)

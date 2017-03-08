# -*- coding: utf-8 -*-
import logging
import os

from cglims.api import ClinicalLims
import click
import ruamel.yaml

from cgadmin.report.core import report
from cgadmin.store import api, models
from cgadmin.log import init_log
from cgadmin import lims

log = logging.getLogger(__name__)


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-c', '--config', type=click.File('r'))
@click.option('-d', '--database', help='SQL connection string')
@click.option('-l', '--log-level', default='INFO')
@click.pass_context
def root(context, config, database, log_level):
    """Interact with the order portal."""
    init_log(logging.getLogger(), loglevel=log_level)
    context.obj = ruamel.yaml.safe_load(config) if config else {}
    context.obj['database'] = (database or context.obj.get('database') or
                               os.environ['CGADMIN_SQL_DATABASE_URI'])
    if 'lims' not in context.obj:
        context.obj['lims'] = {
            'host': os.environ['CGLIMS_HOST'],
            'username': os.environ['CGLIMS_USERNAME'],
            'password': os.environ['CGLIMS_PASSWORD'],
        }
    context.obj['db'] = api.connect(context.obj['database'])


@root.command()
@click.option('-g', '--general', type=click.File('r'), required=True)
@click.option('-c', '--customers', type=click.File('r'), required=True)
@click.pass_context
def setup(context, general, customers):
    """Setup a database from scratch."""
    db = context.obj['db']
    if len(db.engine.table_names()) != 0:
        db.drop_all()
    db.create_all()

    customers_data = ruamel.yaml.safe_load(customers)
    for customer in customers_data:
        db.Customer.save(customer)

    click.echo('all set up!')


@root.command()
@click.option('-s', '--submitted', is_flag=True, help='show submitted')
@click.pass_context
def projects(context, submitted):
    """List projects in the database."""
    db = context.obj['db']
    query = db.Project
    if submitted:
        query = query.filter(models.Project.is_locked)
    for project in query:
        click.echo("{this.id}: {this.name} ({this.customer.customer_id})"
                   .format(this=project))


@root.command()
@click.argument('project_id', type=int)
@click.pass_context
def upload(context, project_id):
    """Create a new LIMS project."""
    new_project = context.obj['db'].Project.get(project_id)
    if not new_project.is_locked:
        click.echo("project not yet submitted ({})".format(new_project.name))
        context.abort()
    elif new_project.lims_id:
        click.echo("project already added to LIMS: {}".format(new_project.lims_id))
        context.abort()
    lims_api = ClinicalLims(context.obj['lims']['host'],
                            context.obj['lims']['username'],
                            context.obj['lims']['password'])
    project_data = api.parse_db_project(new_project)
    lims_project = lims.new_lims_project(context.obj['db'], lims_api, project_data)
    new_project.lims_id = lims_project.id
    context.obj['db'].Project.save(new_project)
    click.echo("added new project to LIMS: {}".format(lims_project.id))


@root.command()
@click.option('-f', '--field', 'fields', multiple=True, help='fields to display')
@click.argument('cust_id')
@click.pass_context
def customer(context, cust_id, fields):
    """Display information about a customer."""
    cust_obj = context.obj['db'].Customer.filter_by(customer_id=cust_id).first()
    if cust_obj is None:
        log.error("can't find customer: %s", cust_id)
        context.abort()
    if fields:
        for field in fields:
            click.echo(getattr(cust_obj, field))
    else:
        raw_output = ruamel.yaml.dump(cust_obj.to_dict(),
                                      Dumper=ruamel.yaml.RoundTripDumper)
        click.echo(raw_output)


root.add_command(report)

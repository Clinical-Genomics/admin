# -*- coding: utf-8 -*-
import os

from cglims.api import ClinicalLims
import click
import ruamel.yaml

from cgadmin.report.core import report
from cgadmin.store import api, models
from cgadmin import lims


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-c', '--config', type=click.File('r'))
@click.option('-d', '--database', help='SQL connection string')
@click.pass_context
def root(context, config, database):
    """Interact with the order portal."""
    context.obj = ruamel.yaml.safe_load(config) if config else {}
    db_uri = (database or context.obj.get('database') or
              os.environ['CGADMIN_SQL_DATABASE_URI'])
    context.obj['db'] = api.connect(db_uri)


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
def process(context, project_id):
    """Create a new LIMS project."""
    new_project = context.obj['db'].Project.get(project_id)
    if not new_project.is_locked:
        click.echo("project not yet submitted")
        context.abort()
    lims_api = ClinicalLims(context.obj['lims']['host'],
                            context.obj['lims']['username'],
                            context.obj['lims']['password'])
    lims_project = lims.add_all(lims_api, new_project)
    click.echo("added new project to LIMS: {}".format(lims_project.id))


root.add_command(report)

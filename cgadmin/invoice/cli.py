# -*- coding: utf-8 -*-
import click

from .render import render_xlsx


@click.command()
@click.argument('invoice_id')
@click.argument('costcenter', type=click.Choice(['kth', 'ki']))
@click.argument('excel_path', type=click.Path())
@click.pass_context
def invoice(context, invoice_id, costcenter, excel_path):
    """Generate an invoice as an Excel sheet."""
    invoice_obj = context.obj['db'].invoice(invoice_id)
    data = invoice_obj.data
    data['project'] = getattr(invoice_obj.customer, "project_account_{}".format(costcenter))
    workbook = render_xlsx(data, costcenter)
    workbook.save(excel_path)

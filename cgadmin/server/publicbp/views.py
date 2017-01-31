# -*- coding: utf-8 -*-
from flask import Blueprint, render_template

blueprint = Blueprint('public', __name__, template_folder='templates',
                      static_folder='static', static_url_path='/public/static')


@blueprint.route('/analyses')
def analyses():
    """View of application tags."""
    return render_template('public/analyses.html')

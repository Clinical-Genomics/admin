# -*- coding: utf-8 -*-
import os
import tempfile

from cglims.api import ClinicalLims
from cglims.apptag import ApplicationTag
import coloredlogs
from flask import (abort, Flask, render_template, request, redirect, url_for,
                   flash, jsonify)
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_bootstrap import Bootstrap
from flask_login import current_user, login_required
from jsonschema import ValidationError
from werkzeug.utils import secure_filename

from cgadmin import constants
from cgadmin.store import models
from cgadmin.store.parse import parse_db_project
from cgadmin.lims import new_lims_project
from cgadmin.orderform import parse_orderform
from .admin import UserManagement
from .flask_sqlservice import FlaskSQLService
from .publicbp import blueprint as public_bp


coloredlogs.install(level='INFO')
app = Flask(__name__)
SECRET_KEY = 'unsafe!!!'
BOOTSTRAP_SERVE_LOCAL = 'FLASK_DEBUG' in os.environ
TEMPLATES_AUTO_RELOAD = True
SQL_DATABASE_URI = os.environ['CGADMIN_SQL_DATABASE_URI']

# user management
GOOGLE_OAUTH_CLIENT_ID = os.environ['GOOGLE_OAUTH_CLIENT_ID']
GOOGLE_OAUTH_CLIENT_SECRET = os.environ['GOOGLE_OAUTH_CLIENT_SECRET']
USER_DATABASE_PATH = os.environ['USER_DATABASE_PATH']
CGLIMS_HOST = os.environ['CGLIMS_HOST']
CGLIMS_USERNAME = os.environ['CGLIMS_USERNAME']
CGLIMS_PASSWORD = os.environ['CGLIMS_PASSWORD']

app.config.from_object(__name__)

db = FlaskSQLService(model_class=models.Model)
user = UserManagement(db)
admin = Admin(name='Clinical Admin', template_mode='bootstrap3')
lims_api = ClinicalLims(CGLIMS_HOST, CGLIMS_USERNAME, CGLIMS_PASSWORD)


@app.route('/', methods=['GET', 'POST'])
def index():
    if not current_user.is_authenticated:
        return render_template('index.html')
    if current_user.customers:
        customer_ids = [customer.id for customer in current_user.customers]
        project_filter = models.Project.customer_id.in_(customer_ids)
        proj_q = db.Project.filter(project_filter)
        customer_q = None
    else:
        customer_q = db.Customer.find()
        proj_q = None
    return render_template('projects.html', projects=proj_q, customers=customer_q)


@app.route('/users/<int:user_id>/link', methods=['POST'])
@login_required
def link_customers(user_id):
    """Link user to a customer."""
    user_obj = db.User.get(user_id)
    for customer_id_str in request.form.getlist('customers'):
        customer_id = int(customer_id_str)
        customer_obj = db.Customer.get(customer_id)
        user_obj.customers.append(customer_obj)
        flash("linked {} to {}".format(user_obj.name, customer_obj.name), 'success')
    db.User.save(user_obj)
    return redirect(url_for('index'))


@app.route('/projects/<int:project_id>')
@login_required
def project(project_id):
    """View a project."""
    project_obj = db.Project.get(project_id)
    apptags = db.ApplicationTag.order_by('category')
    return render_template('project.html', project=project_obj, apptags=apptags,
                           form=request.form)


@app.route('/projects', methods=['POST'])
@app.route('/projects/<int:project_id>', methods=['POST'])
@login_required
def projects(project_id=None):
    """Add a new project to the database."""
    if request.method == 'POST' and request.files['orderform']:
        project_data = collect_project_data()
        submit_lims_project(project_data)
        return redirect(url_for('index'))

    project_data = build_project()
    if project_id:
        project_obj = db.Project.get(project_id)
        project_obj.update(project_data)
        db.Project.save(project_obj)
        flash("project: {} updated".format(project_obj.name), 'info')
    else:
        project_obj = db.Project.save(project_data)
        flash("{} created".format(project_obj.name), 'info')
    return redirect(url_for('project', project_id=project_obj.id))


@app.route('/projects/<int:project_id>/submit', methods=['POST'])
@login_required
def submit_project(project_id):
    """Submit and lock a project."""
    project_obj = db.Project.get(project_id)
    project_data = parse_db_project(project_obj)
    lims_project = submit_lims_project(project_data)
    if lims_project:
        project_obj.is_locked = True
        project_obj.lims_id = lims_project.id
        db.Project.save(project_obj)
        return redirect(url_for('index'))
    else:
        return redirect(url_for('project', project_id=project_obj.id))


@app.route('/projects/<int:project_id>/families', methods=['POST'])
@login_required
def families(project_id):
    """Add a new project to the database."""
    project_obj = db.Project.get(project_id)
    family_data = build_family()
    family_data['project'] = project_obj
    try:
        check_familyname(project_obj.customer.customer_id, family_data['name'])
    except ValueError:
        return redirect(request.referrer)

    try:
        new_family = db.Family.save(family_data)
    except models.DuplicateFamilyNameError as error:
        flash("detected duplicate family name: {}".format(error), 'danger')
        return redirect(url_for('project', project_id=project_obj.id))
    flash("{} created".format(new_family.name), 'info')
    return redirect(url_for('project', project_id=project_id))


@app.route('/families/<int:family_id>', methods=['POST'])
@login_required
def family(family_id):
    """Update a family."""
    family_obj = db.Family.get(family_id)
    family_data = build_family()
    if family_data['name'] != family_obj.name:
        customer_id = family_obj.project.customer.customer_id
        try:
            check_familyname(customer_id, family_data['name'])
        except ValueError:
            return redirect(request.referrer)
    family_obj.update(family_data)
    db.Family.save(family_obj)
    flash("family: {} updated".format(family_obj.name), 'info')
    return redirect(url_for('project', project_id=family_obj.project.id))


@app.route('/families/<int:family_id>/delete', methods=['POST'])
@login_required
def delete_family(family_id):
    """Delete a family."""
    family_obj = db.Family.get(family_id)
    project_id = family_obj.project.id
    if family_obj is None:
        return abort(404, "family not found")
    db.Family.destroy(family_obj)
    return redirect(url_for('project', project_id=project_id))


@app.route('/families/<int:family_id>/samples', methods=['POST', 'GET'])
@app.route('/samples/<int:sample_id>', methods=['POST'])
@login_required
def samples(family_id=None, sample_id=None):
    """Add or update a sample to an existing family."""
    if family_id:
        family_obj = db.Family.get(family_id)
        if family_obj and request.method == 'GET':
            return redirect(url_for('project', project_id=family_obj.project.id))
    elif sample_id:
        sample_obj = db.Sample.get(sample_id)
        family_obj = sample_obj.family
    else:
        return abort(500)

    sample_data = build_sample()
    if sample_data:
        customer_id = family_obj.project.customer.customer_id
        check_samplename(customer_id, sample_data['name'])

        if family_id:
            sample_data['family_id'] = family_id
            sample_obj = db.Sample.save(sample_data)
        elif sample_id:
            sample_obj.update(sample_data)
            db.Sample.save(sample_obj)

        check_triotag(family_obj)
        flash("sample: {} updated".format(sample_obj.name), 'info')
        return redirect(url_for('project', project_id=family_obj.project.id))
    else:
        apptags = db.ApplicationTag.order_by('category')
        return render_template('project.html', project=family_obj.project,
                               apptags=apptags, form=request.form)


@app.route('/api/v1/projects', methods=['POST'])
def api_projects():
    """Submit new projects to LIMS."""
    project_data = request.get_json()
    try:
        lims_project = new_lims_project(db, lims_api, project_data)
    except ValidationError as error:
        flash(error.message, 'error')
        return abort(406)
    return jsonify(success=True, project_id=lims_project.id)


# register blueprints
app.register_blueprint(public_bp)

# hookup extensions to app
db.init_app(app)
user.init_app(app)
Bootstrap(app)
admin.init_app(app)

app.jinja_env.globals.update(db=db, constants=constants)


def collect_project_data():
    """Collect data about a project submission."""
    excel_file = request.files['orderform']
    project_name = request.form['name']
    filename = secure_filename(excel_file.filename)
    temp_dir = tempfile.gettempdir()
    saved_path = os.path.join(temp_dir, filename)
    excel_file.save(saved_path)
    project_data = parse_orderform(saved_path)
    project_data['name'] = project_name
    return project_data


def submit_lims_project(project_data):
    """Handle submission of project to LIMS in Flask context."""
    try:
        lims_project = new_lims_project(db, lims_api, project_data)
    except ValidationError as error:
        message_path = []
        base = project_data
        for step in error.absolute_path:
            if isinstance(step, int):
                message_path.append(base[step]['name'])
            base = base[step]
        message_path.append(step)
        message_path.append(error.message)
        flash(' -> '.join(message_path), 'danger')
        return False
    except ValueError as error:
        flash(error.args[0], 'danger')
        return False
    flash("submitted new project: {}!".format(lims_project.id), 'success')
    return lims_project


class ProtectedModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('login.login', next=request.url))


with app.app_context():
    admin.add_view(ProtectedModelView(models.User, db.session))
    admin.add_view(ProtectedModelView(models.Customer, db.session))
    admin.add_view(ProtectedModelView(models.Project, db.session))
    admin.add_view(ProtectedModelView(models.Family, db.session))
    admin.add_view(ProtectedModelView(models.Sample, db.session))
    admin.add_view(ProtectedModelView(models.ApplicationTag, db.session))
    admin.add_view(ProtectedModelView(models.ApplicationTagVersion, db.session))
    admin.add_view(ProtectedModelView(models.Invoice, db.session))
    admin.add_view(ProtectedModelView(models.Method, db.session))


def build_project():
    """Parse form data."""
    customer = db.Customer.get(int(request.form['customer']))
    project_data = dict(
        name=request.form['name'],
        customer=customer,
        user=current_user,
    )
    return project_data


def build_family():
    """Parse form data for a family."""
    panels = request.form.getlist('panels')
    family_data = dict(
        name=request.form['name'],
        panels=panels,
        priority=request.form['priority'],
        delivery_type=request.form['delivery'],
        require_qcok=(True if request.form.get('require_qcok') == 'on'
                      else False),
    )
    return family_data


def build_sample():
    required_fields = ['name', 'sex', 'application_tag']
    for field in required_fields:
        if not request.form.get(field):
            flash("missing required information: {}".format(field), 'danger')
            return None

    sample_data = dict(
        name=request.form['name'],
        sex=request.form['sex'],
        status=request.form.get('status'),
    )

    apptag_obj = db.ApplicationTag.get(request.form['application_tag'])
    cg_apptag = ApplicationTag(apptag_obj.name)
    sample_data['application_tag'] = apptag_obj

    if not cg_apptag.is_external:
        # if the sample isn't externally sequenced
        if not request.form.get('container'):
            flash('you need to specify "container"', 'warning')
            return None
        if not request.form.get('source'):
            flash('you need to specify "source"', 'warning')
            return None

        sample_data['container'] = request.form['container']
        sample_data['source'] = request.form['source']
        sample_data['quantity'] = request.form.get('quantity')
        if sample_data['container'] == '96 well plate':
            for field in ['container_name', 'well_position']:
                if not request.form.get(field):
                    flash("you need to specify '{}'".format(field), 'warning')
                    return None
                sample_data[field] = request.form[field]
    else:
        if cg_apptag.is_panel:
            # expect capture kit for external samples
            if 'capture_kit' not in request.form:
                flash("external exomes; specify 'capture kit'", 'warning')
                return None
            sample_data['capture_kit'] = request.form['capture_kit']

    for parent_id in ['mother', 'father']:
        if parent_id in request.form:
            parent_sample = db.Sample.get(request.form[parent_id])
            sample_data[parent_id] = parent_sample
    return sample_data


def check_triotag(family_obj):
    """Check if we can update to trio app tag."""
    if len(family_obj.samples) == 3:
        # passed first criteria
        app_tags = set(sample_obj.application_tag for sample_obj in
                       family_obj.samples)
        allowed_tags = set(['WGSPCFC030', 'WGTPCFC030'])
        if len(app_tags.difference(allowed_tags)) == 0:
            # then we can update the application tag for the samples
            message = ("found 3 WGS samples in {}, updated application tag!"
                       .format(family_obj.name))
            flash(message, 'success')
            for sample_obj in family_obj.samples:
                sample_obj.application_tag = 'WGTPCFC030'
                db.Sample.save(sample_obj)


def check_familyname(customer_id, family_name):
    """Check existing families in LIMS."""
    lims_samples = lims_api.get_samples(udf={'customer': customer_id,
                                             'familyID': family_name})
    if len(lims_samples) > 0:
        flash("family name already exists: {}".format(family_name), 'danger')
        raise ValueError(family_name)


def check_samplename(customer_id, sample_name):
    """Check existing families in LIMS."""
    lims_samples = lims_api.get_samples(name=sample_name,
                                        udf={'customer': customer_id})
    if len(lims_samples) > 0:
        flash("sample name already exists: {}".format(sample_name), 'danger')
        return redirect(request.referrer)

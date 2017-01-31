# -*- coding: utf-8 -*-
import os

from cglims.api import ClinicalLims
from flask import (abort, Flask, render_template, request, redirect, url_for,
                   flash)
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_bootstrap import Bootstrap
from flask_login import current_user, login_required

from cgadmin.store import models
from cgadmin import constants
from .admin import UserManagement
from .flask_sqlservice import FlaskSQLService
from .publicbp import blueprint as public_bp


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
lims = ClinicalLims(CGLIMS_HOST, CGLIMS_USERNAME, CGLIMS_PASSWORD)


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
    return render_template('projects.html', constants=constants,
                           projects=proj_q, customers=customer_q)


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
    return render_template('project.html', project=project_obj,
                           constants=constants, apptags=apptags)


@app.route('/projects', methods=['POST'])
@app.route('/projects/<int:project_id>', methods=['POST'])
@login_required
def projects(project_id=None):
    """Add a new project to the database."""
    project_data = build_project()
    if project_id:
        project_obj = db.Project.get(project_id)
        project_obj.update(project_data)
        db.Project.save(project_obj)
        flash("{} updated".format(project_obj.name), 'info')
    else:
        project_obj = db.Project.save(project_data)
        flash("{} created".format(project_obj.name), 'info')
    return redirect(url_for('project', project_id=project_obj.id))


@app.route('/projects/<int:project_id>/submit', methods=['POST'])
def submit_project(project_id):
    """Submit and lock a project."""
    project_obj = db.Project.get(project_id)
    project_obj.is_locked = True
    db.Project.save(project_obj)
    flash("project successfully submitted: {}".format(project_obj.name),
          'success')
    return redirect(url_for('index'))


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


@app.route('/families/<int:family_id>', methods=['GET', 'POST'])
@login_required
def family(family_id):
    """Show a family."""
    family_obj = db.Family.get(family_id)
    if request.method == 'POST':
        # update the family in the database
        family_data = build_family()
        if family_data['name'] != family_obj.name:
            customer_id = family_obj.project.customer.customer_id
            try:
                check_familyname(customer_id, family_data['name'])
            except ValueError:
                return redirect(request.referrer)
        family_obj.update(family_data)
        db.Family.save(family_obj)
        flash("{} updated".format(family_obj.name), 'info')

    apptags = db.ApplicationTag.order_by('category')
    return render_template('family.html', family=family_obj,
                           constants=constants, apptags=apptags)


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


@app.route('/families/<int:family_id>/samples', methods=['POST'])
@app.route('/samples/<int:sample_id>', methods=['POST'])
@login_required
def samples(family_id=None, sample_id=None):
    """Add or update a sample to an existing family."""
    if family_id:
        family_obj = db.Family.get(family_id)
    elif sample_id:
        sample_obj = db.Sample.get(sample_id)
        family_obj = sample_obj.family
    else:
        return abort(500)

    sample_data = build_sample()
    customer_id = family_obj.project.customer.customer_id
    check_samplename(customer_id, sample_data['name'])

    if family_id:
        sample_data['family_id'] = family_id
        sample_obj = db.Sample.save(sample_data)
    elif sample_id:
        sample_obj.update(sample_data)
        db.Sample.save(sample_obj)

    check_triotag(family_obj)
    flash("{} updated".format(sample_obj.name), 'info')
    return redirect(url_for('family', family_id=family_obj.id))


# register blueprints
app.register_blueprint(public_bp)

# hookup extensions to app
db.init_app(app)
user.init_app(app)
Bootstrap(app)
admin.init_app(app)

app.jinja_env.globals.update(db=db)


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
    sample_data = dict(
        name=request.form['name'],
        sex=request.form['sex'],
        status=request.form['status'],
        source=request.form['source'],
        container=request.form['container'],
    )
    apptag_obj = db.ApplicationTag.get(request.form['application_tag'])
    sample_data['application_tag'] = apptag_obj
    if sample_data['container'] == '96 well plate':
        sample_data['container_name'] = request.form['container_name']
        sample_data['container_name'] = request.form['well_position']
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
    lims_samples = lims.get_samples(udf={'customer': customer_id,
                                         'familyID': family_name})
    if len(lims_samples) > 0:
        flash("family name already exists: {}".format(family_name), 'danger')
        raise ValueError(family_name)


def check_samplename(customer_id, sample_name):
    """Check existing families in LIMS."""
    lims_samples = lims.get_samples(name=sample_name,
                                    udf={'customer': customer_id})
    if len(lims_samples) > 0:
        flash("sample name already exists: {}".format(sample_name), 'danger')
        return redirect(request.referrer)

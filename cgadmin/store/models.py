# -*- coding: utf-8 -*-
from datetime import datetime

import ruamel.yaml
from sqlalchemy import Column, types, orm, ForeignKey, UniqueConstraint, Table
from sqlservice import declarative_base, event

from cgadmin import constants
from cgadmin.server.admin import UserManagementMixin

Model = declarative_base()


class DuplicateFamilyNameError(Exception):
    pass


customer_user_link = Table(
    'customer_user_link',
    Model.metadata,
    Column('customer_id', types.Integer, ForeignKey('customer.id'), nullable=False),
    Column('user_id', types.Integer, ForeignKey('user.id'), nullable=False),
    UniqueConstraint('customer_id', 'user_id', name='_customer_user_uc'),
)


class Customer(Model):

    __tablename__ = 'customer'

    id = Column(types.Integer, primary_key=True)
    customer_id = Column(types.String(32), unique=True, nullable=False)
    name = Column(types.String(128), nullable=False)
    agreement_date = Column(types.Date)
    agreement_registration = Column(types.String(32))
    scout_access = Column(types.Boolean)
    primary_contact_id = Column(ForeignKey('user.id'))
    delivery_contact_id = Column(ForeignKey('user.id'))
    uppmax_account = Column(types.String(32))
    project_account_ki = Column(types.String(32))
    project_account_kth = Column(types.String(32))
    organisation_number = Column(types.String(32))
    invoice_address = Column(types.Text)
    invoice_reference = Column(types.String(32))
    invoice_contact_id = Column(ForeignKey('user.id'))

    primary_contact = orm.relationship('User', foreign_keys=[primary_contact_id])
    delivery_contact = orm.relationship('User', foreign_keys=[delivery_contact_id])
    invoice_contact = orm.relationship('User', foreign_keys=[invoice_contact_id])
    invoices = orm.relationship('Invoice', cascade='all,delete', backref='customer')
    users = orm.relationship('User', secondary=customer_user_link, back_populates='customers')
    projects = orm.relationship('Project', cascade='all,delete', backref='customer')

    def __unicode__(self):
        return self.customer_id

    def __str__(self):
        return self.customer_id


class User(Model, UserManagementMixin):

    __tablename__ = 'user'

    is_admin = Column(types.Boolean, default=False)
    projects = orm.relationship('Project', backref='user')
    customers = orm.relationship('Customer', secondary=customer_user_link, back_populates='users')

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Project(Model):

    __tablename__ = 'project'
    __table_args__ = (
        UniqueConstraint('customer_id', 'name', name='_customer_name_uc'),
    )

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(128), nullable=False)
    customer_id = Column(ForeignKey(Customer.id), nullable=False)
    created_at = Column(types.DateTime, default=datetime.now)
    user_id = Column(ForeignKey(User.id), nullable=False)
    is_locked = Column(types.Boolean)
    lims_id = Column(types.String(32))

    families = orm.relationship('Family', cascade='all,delete', backref='project')

    @property
    def samples(self):
        """Return all the samples."""
        for family_obj in self.families:
            for sample_obj in family_obj.samples:
                yield sample_obj

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Family(Model):

    __tablename__ = 'family'

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(64), nullable=False)
    _panels = Column(types.Text)
    priority = Column(types.Enum(*constants.PRIORITIES), nullable=False)
    delivery_type = Column(types.Enum(*constants.DELIVERY_TYPES), nullable=False)
    require_qcok = Column(types.Boolean, default=False)
    existing_family = Column(types.Boolean, default=False)
    keep_vis = Column(types.Boolean, default=False)

    project_id = Column(ForeignKey(Project.id), nullable=False)
    samples = orm.relationship('Sample', cascade='all,delete', backref='family',
                               order_by='Sample.id')

    @event.before_save()
    def before_save(mapper, connection, target):
        query = """
            SELECT * FROM family
            INNER JOIN project ON family.project_id = project.id
            WHERE family.name = "{}"
            AND project.customer_id = "{}"
        """.format(target.name, target.project.customer_id)
        if target.id:
            query += """AND family.id != {}""".format(target.id)
        if connection.scalar(query) == 1:
            raise DuplicateFamilyNameError(target.name)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    @property
    def panels(self):
        """Return a list of panels."""
        panel_list = self._panels.split(',') if self._panels else []
        return panel_list

    @panels.setter
    def panels(self, panel_list):
        self._panels = ','.join(panel_list) if panel_list else None

    @property
    def suggested_tag(self):
        """Suggest an application tag based on existing samples."""
        for sample in self.samples:
            if sample.application_tag:
                return sample.application_tag


class Sample(Model):

    __tablename__ = 'sample'
    __table_args__ = (UniqueConstraint('family_id', 'name',
                                       name='_family_name_uc'),)

    id = Column(types.Integer, primary_key=True)
    family_id = Column(ForeignKey(Family.id), nullable=False)
    name = Column(types.String(64), nullable=False)
    sex = Column(types.Enum(*constants.SEXES))
    status = Column(types.Enum(*constants.STATUSES))
    apptag_id = Column(ForeignKey('applicationtag.id'))
    source = Column(types.Enum(*constants.SOURCES))
    container = Column(types.Enum(*constants.CONTAINERS))
    well_position = Column(types.Enum(*constants.WELL_POSITIONS))
    container_name = Column(types.String(64))
    capture_kit = Column(types.Enum(*constants.CAPTURE_KITS))
    quantity = Column(types.Integer)
    mother_id = Column(ForeignKey('sample.id'))
    father_id = Column(ForeignKey('sample.id'))
    comment = Column(types.Text)
    existing_sample = Column(types.Boolean, default=False)
    exclude_analysis = Column(types.Boolean, default=False)

    mother = orm.relationship('Sample', remote_side=[id], foreign_keys=[mother_id])
    father = orm.relationship('Sample', remote_side=[id], foreign_keys=[father_id])

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class ApplicationTag(Model):

    __tablename__ = 'applicationtag'

    id = Column(types.Integer, primary_key=True)
    category = Column(types.Enum(*constants.APPLICATION_CATEGORIES), nullable=False)
    name = Column(types.String(32), unique=True, nullable=False)
    created_at = Column(types.DateTime, default=datetime.now)
    minimum_order = Column(types.Integer)
    sequencing_depth = Column(types.Integer)
    sample_amount = Column(types.Integer)
    sample_volume = Column(types.String(64))
    sample_concentration = Column(types.String(64))
    turnaround_time = Column(types.Integer)
    priority_processing = Column(types.Boolean)

    last_updated = Column(types.DateTime, onupdate=datetime.now)
    comment = Column(types.Text)

    versions = orm.relationship('ApplicationTagVersion',
                                order_by='ApplicationTagVersion.version',
                                backref='apptag')
    samples = orm.relationship('Sample', backref='application_tag')

    @property
    def latest(self):
        return self.versions[0] if self.versions else None

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class ApplicationTagVersion(Model):

    __tablename__ = 'applicationtag_version'
    __table_args__ = (UniqueConstraint('apptag_id', 'version',
                                       name='_apptag_version_uc'),)

    id = Column(types.Integer, primary_key=True)
    version = Column(types.Integer, nullable=False)
    apptag_id = Column(ForeignKey(ApplicationTag.id), nullable=False)
    valid_from = Column(types.DateTime, default=datetime.now, nullable=False)
    price_standard = Column(types.Integer)
    price_priority = Column(types.Integer)
    price_express = Column(types.Integer)
    price_reserach = Column(types.Integer)
    is_accredited = Column(types.Boolean)
    description = Column(types.Text)
    limitations = Column(types.Text)
    percent_kth = Column(types.Integer)

    last_updated = Column(types.DateTime, onupdate=datetime.now)
    comment = Column(types.Text)

    def __unicode__(self):
        return "{}:{}".format(self.apptag.name, self.version)

    def __str__(self):
        return "{}:{}".format(self.apptag.name, self.version)


class Method(Model):

    __tablename__ = 'method'
    __table_args__ = (UniqueConstraint('document', 'document_version',
                                       name='_document_version_uc'),)

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(128), nullable=False)
    document = Column(types.Integer, nullable=False)
    document_version = Column(types.Integer, nullable=False)
    description = Column(types.Text, nullable=False)
    limitations = Column(types.Text)

    last_updated = Column(types.DateTime, onupdate=datetime.now)
    comment = Column(types.Text)

    @property
    def full_name(self):
        """Return the full name with number and version."""
        return "{this.document}:{this.document_version} {this.name}".format(this=self)

    def __unicode__(self):
        return self.full_name

    def __str__(self):
        return self.full_name


class Invoice(Model):

    __tablename__ = 'invoice'

    id = Column(types.Integer, primary_key=True)
    customer_id = Column(ForeignKey(Customer.id), nullable=False)
    invoice_id = Column(types.String(32), nullable=False, unique=True)
    invoiced_at = Column(types.Date, default=datetime.now)
    sent_at = Column(types.DateTime)
    costcenter = Column(types.Enum('kth', 'ki'))
    comment = Column(types.Text)
    excel_file_kth = Column(types.BLOB)
    excel_file_ki = Column(types.BLOB)
    _data = Column(types.Text)

    @property
    def data(self):
        """Store data for an invoice as a YAML string."""
        yaml_data = ruamel.yaml.safe_load(self._data) if self._data else {}
        return yaml_data

    @data.setter
    def data(self, yaml_data):
        self._data = ruamel.yaml.dump(yaml_data) if yaml_data else None

# -*- coding: utf-8 -*-
import logging
from xml.etree import ElementTree

from cglims.apptag import ApplicationTag
from genologics.entities import (Project, Researcher, Sample, Container,
                                 Containertype)
from jsonschema import validate
from cgadmin.schema import schema_project

SEX_MAP = {'male': 'M', 'female': 'F', 'unknown': 'unknown'}
CON_TYPES = {'Tube': 2, '96 well plate': 1}
log = logging.getLogger(__name__)


def new_lims_project(admin_db, lims_api, project_data):
    """Create a new project with samples in LIMS."""
    validate(project_data, schema_project)
    prepare_data(admin_db, project_data)
    for family_data in project_data['families']:
        check_family(lims_api, family_data)
        for sample_data in family_data['samples']:
            log.debug("checking sample: %s", sample_data['name'])
            check_sample(lims_api, sample_data)

    lims_project = make_project(lims_api, project_data, researcher_id='3')
    log.info("added new LIMS project: %s", lims_project.id)

    container_groups = group_containers(project_data)
    for container_name, samples in container_groups.items():
        lims_container = make_container(lims_api, container_name)
        for sample_data in samples:
            lims_sample = make_sample(lims_api, sample_data, lims_project,
                                      lims_container)
            log.info("added new LIMS sample: %s", lims_sample.id)

    return lims_project


def check_sample(lims_api, sample_data):
    """Check sample data before inserting into LIMS."""
    lims_samples = lims_api.get_samples(name=sample_data['name'],
                                        udf={'customer': sample_data['customer']})
    # TODO: could add check if other samples are canceled...
    if len(lims_samples) > 0:
        raise ValueError("duplicate sample name: {}".format(sample_data['name']))

    family_id = sample_data['family']['name']
    lims_samples = lims_api.get_samples(udf={'customer': sample_data['customer'],
                                             'familyID': family_id})
    if len(lims_samples) > 0:
        raise ValueError("duplicate family name: {}".format(family_id))

    if sample_data['is_external']:
        if sample_data['apptag'].is_panel and sample_data.get('capture_kit') is None:
            raise ValueError("external exome samples needs 'capture kit'!")
    else:
        if sample_data.get('container') is None:
            raise ValueError("non-external sample missing 'container': {}"
                             .format(sample_data['name']))
        if sample_data.get('source') is None:
            raise ValueError("non-external sample missing 'source': {}"
                             .format(sample_data['name']))

    if sample_data['family']['delivery_type'] == 'scout':
        log.debug("sample intended for Scout upload, checking required fields")
        if sample_data.get('status') is None:
            raise ValueError("sample needs 'status' for upload to Scout: {}"
                             .format(sample_data['name']))


def check_family(lims_api, family_data):
    """Check family data, mostly relationships."""
    if len(family_data['samples']) > 1:
        relations = [sample_data for sample_data in family_data['samples']
                     if (sample_data.get('mother') or sample_data.get('father'))]
        if len(relations) == 0:
            family_id = family_data['name']
            raise ValueError("samples in family not related: {}".format(family_id))

        sample_map = {sample_data['name'] for sample_data in family_data['samples']}
        for sample_data in relations:
            for parent_key in ('mother', 'father'):
                parent_id = sample_data[parent_key]
                if parent_id and parent_id not in sample_map:
                    sample_name = sample_data['name']
                    raise ValueError("sample relation error: {}, {} -> {}"
                                     .format(sample_name, parent_key, parent_id))

    if family_data['delivery_type'] == 'scout':
        if 'panels' not in family_data:
            raise ValueError("family needs 'gene panel' for upload to Scout: {}"
                             .format(family_data['name']))


def prepare_data(admin_db, project_data):
    """Prepare the data before processing it."""
    for family_data in project_data['families']:
        for sample_data in family_data['samples']:
            apptag_name = sample_data['application_tag']
            apptag_obj = admin_db.ApplicationTag.filter_by(name=apptag_name).first()
            if apptag_obj is None:
                raise ValueError("unknown application tag: {}".format(apptag_name))
            sample_data['is_external'] = apptag_obj.is_external
            sample_data['apptag'] = ApplicationTag(apptag_name)
            sample_data['application_tag_version'] = apptag_obj.versions[0].version
            sample_data['family'] = family_data
            sample_data['customer'] = project_data['customer']


def group_containers(project_data):
    """Group samples based on container."""
    container_groups = {}
    for family_data in project_data['families']:
        for sample_data in family_data['samples']:
            if sample_data['is_external'] or sample_data['container'] == 'Tube':
                container_name = sample_data['container_name'] or sample_data['name']
                container_name_full = "tube_{}".format(container_name)
                container_groups[container_name_full] = [sample_data]
            elif sample_data['container'] == '96 well plate':
                if sample_data['container_name'] not in container_groups:
                    container_groups[sample_data['container_name']] = []
                container_groups[sample_data['container_name']].append(sample_data)
            else:
                raise ValueError("unsupported container: {}"
                                 .format(sample_data['container']))
    return container_groups


def make_project(lims_api, project_data, researcher_id='3'):
    """Create a new project with samples."""
    researcher = Researcher(lims_api, id=researcher_id)
    log.info("using researcher: %s", researcher.name)

    # create a new LIMS project
    new_limsproject = Project.create(lims_api, researcher=researcher,
                                     name=project_data['name'])
    # add UDFs
    customer_udf = 'Customer project reference'
    new_limsproject.udf[customer_udf] = project_data['customer']
    new_limsproject.put()
    return new_limsproject


def make_container(lims_api, container_name):
    """Create a new container in LIMS."""
    if container_name.startswith('tube_'):
            container_type = Containertype(lims=lims_api, id='2')
            container_name = container_name.replace('tube_', '')
    else:
        container_type = Containertype(lims=lims_api, id='1')
    lims_container = Container.create(lims=lims_api, name=container_name,
                                      type=container_type)
    log.info("added new LIMS container: %s", lims_container.id)
    return lims_container


def make_sample(lims_api, sample_data, lims_project, lims_container):
    """Create a new sample in LIMS."""
    lims_sample = Sample._create(lims_api, creation_tag='samplecreation',
                                 name=sample_data['name'], project=lims_project)
    add_sample_udfs(lims_sample, sample_data)
    position = sample_data.get('well_position') or '1:1'
    lims_sample = save_sample(lims_api, lims_sample, lims_container, position)
    return lims_sample


def add_sample_udfs(lims_sample, sample_data):
    """Determine sample UDFs."""
    family_data = sample_data['family']
    lims_sample.udf['priority'] = family_data['priority']
    lims_sample.udf['Data Analysis'] = family_data['delivery_type']
    lims_sample.udf['Gene List'] = ';'.join(family_data['panels'])
    lims_sample.udf['Gender'] = SEX_MAP.get(sample_data['sex'])
    lims_sample.udf['Status'] = sample_data['status']
    lims_sample.udf['Sequencing Analysis'] = sample_data['application_tag']
    lims_sample.udf['Application Tag Version'] = sample_data['application_tag_version']
    lims_sample.udf['Source'] = sample_data['source'] or 'NA'
    lims_sample.udf['familyID'] = family_data['name']
    lims_sample.udf['customer'] = sample_data['customer']
    for parent_id in ['mother', 'father']:
        parent_sample = sample_data.get(parent_id)
        if parent_sample:
            lims_sample.udf["{}ID".format(parent_id)] = parent_sample

    lims_sample.udf['Reads missing (M)'] = sample_data['apptag'].reads
    lims_sample.udf['Capture Library version'] = sample_data.get('capture_kit', 'NA')
    require_qcok = 'yes' if family_data['require_qcok'] else 'no'
    lims_sample.udf['Process only if QC OK'] = require_qcok
    lims_sample.udf['Quantity'] = sample_data.get('quantity', 'NA')

    # fill in additional defaults...
    lims_sample.udf['Concentration (nM)'] = 'NA'
    lims_sample.udf['Volume (uL)'] = 'NA'
    lims_sample.udf['Strain'] = 'NA'
    lims_sample.udf['Index type'] = 'NA'
    lims_sample.udf['Index number'] = 'NA'
    lims_sample.udf['Sample Buffer'] = 'NA'
    lims_sample.udf['Reference Genome Microbial'] = 'NA'


def save_sample(lims_api, instance, container, position):
    """Create an instance of Sample from attributes then post it to the LIMS"""
    location = ElementTree.SubElement(instance.root, 'location')
    ElementTree.SubElement(location, 'container', dict(uri=container.uri))
    position_element = ElementTree.SubElement(location, 'value')
    position_element.text = position
    data = lims_api.tostring(ElementTree.ElementTree(instance.root))
    instance.root = lims_api.post(uri=lims_api.get_uri(Sample._URI), data=data)
    instance._uri = instance.root.attrib['uri']
    return instance

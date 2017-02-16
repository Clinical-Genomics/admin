# -*- coding: utf-8 -*-
import logging
from xml.etree import ElementTree

from cglims.apptag import ApplicationTag
from genologics.entities import (Project, Researcher, Sample, Container,
                                 Containertype)

SEX_MAP = {'male': 'M', 'female': 'F', 'unknown': 'unknown'}
CON_TYPES = {'Tube': 2, '96 well plate': 1}
log = logging.getLogger(__name__)


def add_all(lims, new_project):
    """Join all the functions."""
    lims_project = add_project(lims, new_project)
    log.info("added new LIMS project: %s", lims_project.id)

    # group samples based on container
    container_groups = {}
    for new_family in new_project.families:
        for new_sample in new_family.samples:
            if new_sample.is_external or new_sample.container == 'Tube':
                container_name = new_sample.container_name or new_sample.name
                container_name_full = "tube_{}".format(container_name)
                container_groups[container_name_full] = [new_sample]
            elif new_sample.container == '96 well plate':
                if new_sample.container_name not in container_groups:
                    container_groups[new_sample.container_name] = []
                container_groups[new_sample.container_name].append(new_sample)
            else:
                raise ValueError("unsupported container: {}"
                                 .format(new_sample.container))

    for container_name, new_samples in container_groups.items():
        if container_name.startswith('tube_'):
            container_type = Containertype(lims=lims, id='2')
            container_name = container_name.replace('tube_', '')
        else:
            container_type = Containertype(lims=lims, id='1')
        lims_container = Container.create(lims=lims, name=container_name,
                                          type=container_type)
        log.info("added new LIMS container: %s", lims_container.id)

        log.debug("adding new sample: %s", new_sample.name)
        lims_sample = add_sample(lims, lims_project, new_sample, lims_container)
        log.info("added new LIMS sample: %s", lims_sample.id)

    return lims_project


def add_project(lims, new_project, researcher_id='3'):
    """Create a new project with samples."""
    researcher = Researcher(lims, id=researcher_id)
    log.info("using researcher: %s", researcher.name)

    # create a new LIMS project
    new_limsproject = Project.create(lims, researcher=researcher,
                                     name=new_project.name)
    # add UDFs
    customer_udf = 'Customer project reference'
    new_limsproject.udf[customer_udf] = new_project.customer.customer_id
    new_limsproject.put()
    return new_limsproject


def add_sample(lims, lims_project, new_sample, lims_container):
    """Add a new sample to the project."""
    lims_sample = Sample._create(lims, creation_tag='samplecreation',
                                 name=new_sample.name, project=lims_project)
    add_sample_udfs(new_sample, lims_sample)
    position = new_sample.well_position or '1:1'
    lims_sample = save_sample(lims, lims_sample, lims_container, position)
    return lims_sample


def add_sample_udfs(new_sample, lims_sample):
    """Determine sample UDFs."""
    new_family = new_sample.family
    lims_sample.udf['priority'] = new_family.priority
    lims_sample.udf['Data Analysis'] = new_family.delivery_type
    lims_sample.udf['Gene List'] = ';'.join(new_family.panels)
    lims_sample.udf['Gender'] = SEX_MAP.get(new_sample.sex)
    lims_sample.udf['Status'] = new_sample.status
    lims_sample.udf['Sequencing Analysis'] = new_sample.application_tag.name
    latest_version = new_sample.application_tag.versions[0]
    lims_sample.udf['Application Tag Version'] = latest_version.version
    lims_sample.udf['Source'] = new_sample.source or 'NA'
    lims_sample.udf['familyID'] = new_family.name
    lims_sample.udf['customer'] = new_family.project.customer.customer_id
    for parent_id in ['mother', 'father']:
        parent_sample = getattr(new_sample, parent_id)
        if parent_sample:
            lims_sample.udf["{}ID".format(parent_id)] = parent_sample.name

    app_tag = ApplicationTag(new_sample.application_tag)
    lims_sample.udf['Reads missing (M)'] = app_tag.reads

    # fill in additional defaults...
    lims_sample.udf['Capture Library version'] = new_sample.capture_kit or 'NA'
    lims_sample.udf['Concentration (nM)'] = 'NA'
    lims_sample.udf['Volume (uL)'] = 'NA'
    lims_sample.udf['Strain'] = 'NA'
    lims_sample.udf['Index type'] = 'NA'
    lims_sample.udf['Index number'] = 'NA'
    lims_sample.udf['Sample Buffer'] = 'NA'
    lims_sample.udf['Reference Genome Microbial'] = 'NA'
    lims_sample.udf['Process only if QC OK'] = 'NA'


def save_sample(lims, instance, container, position):
    """Create an instance of Sample from attributes then post it to the LIMS"""
    location = ElementTree.SubElement(instance.root, 'location')
    ElementTree.SubElement(location, 'container', dict(uri=container.uri))
    position_element = ElementTree.SubElement(location, 'value')
    position_element.text = position
    data = lims.tostring(ElementTree.ElementTree(instance.root))
    instance.root = lims.post(uri=lims.get_uri(Sample._URI), data=data)
    instance._uri = instance.root.attrib['uri']
    return instance

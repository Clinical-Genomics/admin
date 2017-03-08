# -*- coding: utf-8 -*-
from cgadmin import constants

schema_sample = {
    "title": "Sample",
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9.-]*$"
        },
        "sex": {
            "enum": constants.SEXES
        },
        "status": {
            "enum": constants.STATUSES
        },
        "application_tag": {
            "type": "string"
        },
        "capture_kit": {
            "enum": constants.CAPTURE_KITS
        },
        "father": {
            "type": "string"
        },
        "mother": {
            "type": "string"
        },
        "source": {
            "enum": constants.SOURCES
        },
        "container": {
            "enum": constants.CONTAINERS
        },
        "container_name": {
            "type": "string"
        },
        "well_position": {
            "type": "string",
            "pattern": "^[A-Z]:[1-9]{1,2}$"
        },
        "quantity": {
            "type": "number"
        }
    },
    "required": ["name", "sex", "application_tag"]
}

schema_family = {
    "title": "Family",
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9.-]*$"
        },
        "panels": {
            "type": "array",
            "items": {
                "enum": constants.PANELS,
            },
            "minItems": 1,
            "uniqueItems": True
        },
        "priority": {
            "enum": constants.PRIORITIES
        },
        "delivery_type": {
            "enum": constants.DELIVERY_TYPES
        },
        "require_qcok": {
            "type": "boolean"
        },
        "samples": {
            "type": "array",
            "items": schema_sample
        }
    },
    "required": ["name", "priority"]
}

schema_project = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Project",
    "description": "Submission of new samples to Clinical Genomics",
    "type": "object",
    "properties": {
        "name": {
            "type": "string"
        },
        "customer": {
            "type": "string"
        },
        "families": {
            "type": "array",
            "items": schema_family
        }
    },
    "required": ["name", "customer"]
}

# -*- coding: utf-8 -*-
from wtforms_alchemy import ModelForm

from cgadmin.store.models import Project


class ProjectForm(ModelForm):
    class Meta:
        model = Project

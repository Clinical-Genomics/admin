# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


def parse_reqs(req_path='./requirements.txt'):
    """Recursively parse requirements from nested pip files."""
    install_requires = []
    with open(req_path, 'r') as handle:
        # remove comments and empty lines
        lines = (line.strip() for line in handle
                 if line.strip() and not line.startswith('#'))
        for line in lines:
            # check for nested requirements files
            if line.startswith('-r'):
                # recursively call this function
                install_requires += parse_reqs(req_path=line[3:])
            else:
                # add the line as a new requirement
                install_requires.append(line)
    return install_requires


setup(name='cgadmin',
      version='0.0.1',
      description='Admin interface and order portal',
      url='https://github.com/Clinical-Genomics/cgadmin',
      author='Robin Andeer',
      author_email='robin.andeer@scilifelab.se',
      license='MIP',
      install_requires=parse_reqs(),
      packages=find_packages(exclude=('tests*', 'docs')),
      zip_safe=False,
      include_package_data=True,
      entry_points={
          'console_scripts': [
              'cgadmin = cgadmin.cli:root',
          ],
      })

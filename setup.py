#!/usr/bin/python
# coding: utf-8

import os
from setuptools import setup, find_packages

cur_dir = os.path.abspath(os.path.dirname(__file__))

version_ns = {}
with open(os.path.join(cur_dir, 'version.py')) as f:
    exec(f.read(), {}, version_ns)

long_description = open('README.rst').read()
setup(
    name='ldap_hooks',
    version=version_ns['__version__'],
    description="A set of Jupyter Spawner pre_spawn_hooks for "
    "creating/retrieving LDAP DIT entries during spawn",
    long_description=long_description,
    author="Rasmus Munk",
    author_email="munk1@live.dk",
    packages=find_packages(),
    url="https://github.com/rasmunk/ldap_hooks",
    license="MIT",
    keywords=['Web', 'JupyterHub', 'Spawner', 'Hook'],
    install_requires=[
        'ldap3>=2.5.2',
        'traitlets>=4.3.2',
        'tornado==5.1.1',
        'gen>=0.1'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)

import os
from setuptools import setup, find_packages

cur_dir = os.path.abspath(os.path.dirname(__file__))

version_ns = {}
with open(os.path.join(cur_dir, 'version.py')) as f:
    exec(f.read(), {}, version_ns)

setup(
    name='ldap_hooks',
    version=version_ns['__version__'],
    description="""
    """,
    packages=find_packages(),
    install_requires=[
        'ldap3>=2.5.2',
        'traitlets>=4.3.2',
        'gen>=0.1'
    ]
)

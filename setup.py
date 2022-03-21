import os
from setuptools import setup, find_packages

here = os.path.dirname(__file__)


def read(path):
    with open(path, "r") as _file:
        return _file.read()


def read_req(name):
    path = os.path.join(here, name)
    return [req.strip() for req in read(path).splitlines() if req.strip()]


version_ns = {}
with open(os.path.join(here, "version.py")) as f:
    exec(f.read(), {}, version_ns)

long_description = open("README.rst").read()
setup(
    name="ldap_hooks",
    version=version_ns["__version__"],
    description="A set of Jupyter Spawner pre_spawn_hooks for "
    "creating/retrieving LDAP DIT entries during spawn",
    long_description=long_description,
    author="Rasmus Munk",
    author_email="munk1@live.dk",
    packages=find_packages(),
    url="https://github.com/rasmunk/ldap_hooks",
    license="MIT",
    keywords=["Web", "JupyterHub", "Spawner", "Hook"],
    install_requires=read_req("requirements.txt"),
    extras_require={
        "test": read_req("tests/requirements.txt"),
        "dev": read_req("requirements-dev.txt"),
    },
    project_urls={"Source Code": "https://github.com/rasmunk/ldap_hooks"},
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)

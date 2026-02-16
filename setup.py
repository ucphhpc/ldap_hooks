import os
from setuptools import setup, find_packages


cur_dir = os.path.realpath(os.path.dirname(__file__))


def read(path):
    with open(path, "r") as _file:
        return _file.read()


def read_req(name):
    path = os.path.join(cur_dir, name)
    return [req.strip() for req in read(path).splitlines() if req.strip()]


version_ns = {}
version_path = os.path.join(cur_dir, "ldap_hooks", "_version.py")
version_content = read(version_path)
exec(version_content, {}, version_ns)

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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)

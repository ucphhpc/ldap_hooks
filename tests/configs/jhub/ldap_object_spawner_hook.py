"""A simple jupyter config file for testing the authenticator."""

from ldap_hooks import setup_ldap_entry_hook
from ldap_hooks import LDAP, SPAWNER_USER_ATTRIBUTE, LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY

c = get_config()

c.JupyterHub.ip = "0.0.0.0"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.authenticator_class = "jhubauthenticators.HeaderAuthenticator"
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = "jupyter/base-notebook:latest"
c.DockerSpawner.network_name = "jhub_ldap_network"
# Due a change in how the DockerSpawner escapes usernames in >=12.0.0
# https://jupyterhub-dockerspawner.readthedocs.io/en/latest/changelog.html#id1
# The - character is the new escape character, meaning that the
# usage of the - character will be automatically escaped by the escape string '-d2'
c.DockerSpawner.escape = "legacy"

# Allow .data to be set by authenticated users
c.HeaderAuthenticator.user_external_allow_attributes = ["data"]

c.Spawner.pre_spawn_hook = setup_ldap_entry_hook

# Connection settings
LDAP.url = "openldap"
LDAP.user = "cn=admin,dc=example,dc=org"
LDAP.password = "dummyldap_password"
LDAP.base_dn = "dc=example,dc=org"

# DN attribute settings
LDAP.submit_spawner_attribute = "user.data"
LDAP.submit_spawner_attribute_keys = ("PersonDN",)
LDAP.replace_object_with = {"/": "+"}

LDAP.dynamic_attributes = {
    "name": SPAWNER_USER_ATTRIBUTE,
    "uid": LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY,
}

LDAP.set_spawner_attributes = {"environment": {"NB_USER": "{uid}"}}

# Attributes used to check whether the ldap data
# of type object_classes already exists
LDAP.unique_object_attributes = ["CN"]

# Submit object settings
LDAP.object_classes = ["InetOrgPerson", "PosixAccount"]
LDAP.object_attributes = {
    "uid": "{name}",
    "uidNumber": "1000 ",
    "gidNumber": "100",
    "homeDirectory": "/home/{name}",
}

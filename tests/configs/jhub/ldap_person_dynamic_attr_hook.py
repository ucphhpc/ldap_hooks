"""A simple jupyter config file for testing the authenticator."""
from ldap_hooks import setup_ldap_entry_hook
from ldap_hooks import LDAP, SPAWNER_SUBMIT_DATA

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

# Extract attribute from the SPAWNER submit post
LDAP.dynamic_attributes = {"description": SPAWNER_SUBMIT_DATA}

LDAP.set_spawner_attributes = {
    "environment": {
        "description": "{description}",
        "static_description": "Static description",
    }
}

# LDAP DIT object definition
LDAP.object_classes = ["Person"]
LDAP.object_attributes = {"description": "{description}"}

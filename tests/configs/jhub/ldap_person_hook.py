"""A simple jupyter config file for testing the authenticator."""
from ldap_hooks import setup_ldap_entry_hook
from ldap_hooks import LDAP
c = get_config()

c.JupyterHub.hub_ip = '0.0.0.0'

c.JupyterHub.authenticator_class = 'jhubauthenticators.HeaderAuthenticator'
c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
c.DockerSpawner.image = 'jupyter/base-notebook:latest'
c.DockerSpawner.network_name = 'jhub_ldap_network'

# Allow .data to be set by authenticated users
c.HeaderAuthenticator.user_external_allow_attributes = ['data']

c.Spawner.pre_spawn_hook = setup_ldap_entry_hook

# Connection settings
LDAP.url = 'openldap'
LDAP.user = 'cn=admin,dc=example,dc=org'
LDAP.password = 'dummyldap_password'
LDAP.base_dn = 'dc=example,dc=org'

# DN attribute settings
LDAP.submit_spawner_attribute = 'user.data'
LDAP.submit_spawner_attribute_keys = ('PersonDN',)
LDAP.replace_object_with = {'/': '+'}

# LDAP DIT object definition
LDAP.object_classes = ['Person']
LDAP.object_attributes = {'description': 'A default person account'}

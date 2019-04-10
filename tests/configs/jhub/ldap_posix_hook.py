"""A simple jupyter config file for testing the authenticator."""
from ldap_hooks import setup_ldap_entry_hook
from ldap_hooks import LDAP, LDAP_SEARCH_ATTRIBUTE_QUERY
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

LDAP.dynamic_attributes = {
    'uidNumber': LDAP_SEARCH_ATTRIBUTE_QUERY
}

LDAP.set_spawner_attributes = {
    'environment': {'NB_UID': '{uidNumber}'}
}

LDAP.search_attribute_queries = [
    {'search_base': LDAP.base_dn,
     'search_filter': '(objectclass=X-nextUserIdentifier)',
     'attributes': ['uidNumber']}
]

# LDAP DIT object definition
LDAP.object_classes = ['Person', 'PosixAccount']
LDAP.object_attributes = {
    'uidNumber': '{uidNumber}',
    'gidNumber': '100'
}

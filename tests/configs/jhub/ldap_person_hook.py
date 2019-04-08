"""A simple jupyter config file for testing the authenticator."""
# from ldap_hooks import setup_ldap_entry_hook
# from ldap_hooks import LDAP
c = get_config()

c.JupyterHub.authenticator_class = 'jhubauthenticators.HeaderAuthenticator'
c.JupyterHub.spawner_class = 'dockerspawner.Dockerspawner'

# c.Spawner.pre_spawn_hook = setup_ldap_entry_hook

# LDAP.url = 'http://127.0.0.1'
# LDAP.user = 'cn=admin,dc=example,dc=org'
# LDAP.password = 'dummyldap_password'

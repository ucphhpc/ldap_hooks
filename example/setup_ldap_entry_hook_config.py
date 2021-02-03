# Example config
from jhubauthenticators import RegexUsernameParser
from ldap_hooks import setup_ldap_entry_hook
from ldap_hooks import (
    LDAP,
    LDAP_SEARCH_ATTRIBUTE_QUERY,
    SPAWNER_SUBMIT_DATA,
    INCREMENT_ATTRIBUTE,
    LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY,
)

c = get_config()

c.JupyterHub.ip = "0.0.0.0"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.port = 80

# Spawner setup
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.image = "nielsbohr/base-notebook:latest"
c.DockerSpawner.pre_spawn_hook = setup_ldap_entry_hook

# Authenticator setup
c.JupyterHub.authenticator_class = "jhubauthenticators.HeaderAuthenticator"
c.HeaderAuthenticator.enable_auth_state = True
c.HeaderAuthenticator.allowed_headers = {"auth": "Remote-User"}
c.HeaderAuthenticator.header_parser_classes = {"auth": RegexUsernameParser}
c.HeaderAuthenticator.user_external_allow_attributes = ["data"]
# Email regex
RegexUsernameParser.username_extract_regex = (
    "([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]" "+\.[a-zA-Z0-9-.]+)"
)

# Define LDAP connection options
LDAP.url = "openldap"
LDAP.user = "cn=admin,dc=migrid,dc=org"
LDAP.password = "dummyldap_password"
LDAP.base_dn = "dc=migrid,dc=org"

# LDAP get dn to submit to the DIT
LDAP.submit_spawner_attribute = "user.data"
LDAP.submit_spawner_attribute_keys = ("User", "CERT")

# Prepare LDAP object
LDAP.replace_object_with = {"/": "+"}

# Dynamic attributes and where to find the value
LDAP.dynamic_attributes = {
    "uid": LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY,
    "emailAddress": SPAWNER_SUBMIT_DATA,
    "uidNumber": LDAP_SEARCH_ATTRIBUTE_QUERY,
}

LDAP.set_spawner_attributes = {
    "environment": {"NB_USER": "{uid}", "NB_UID": "{uidNumber}"},
}

# Attributes used to check whether the ldap data
# of type object_classes already exists
LDAP.unique_object_attributes = ["uid"]
LDAP.search_attribute_queries = [
    {
        "search_base": LDAP.base_dn,
        "search_filter": "(objectclass=X-nextUserIdentifier)",
        "attributes": ["uidNumber"],
    }
]

modify_dn = "cn=uidNext" + "," + LDAP.base_dn
LDAP.search_result_operations = {
    "uidNumber": {"action": INCREMENT_ATTRIBUTE, "modify_dn": modify_dn}
}

# Submit object settings
LDAP.object_classes = ["X-certsDistinguishedName", "PosixAccount"]
LDAP.object_attributes = {
    "uid": "{uid}",
    "uidNumber": "{uidNumber}",
    "gidNumber": "100",
    "homeDirectory": "/home/{uid}",
}

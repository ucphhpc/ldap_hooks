.. image:: https://travis-ci.org/rasmunk/ldap_hooks.svg?branch=master
    :target: https://travis-ci.org/rasmunk/ldap_hooks

==========
ldap_hooks
==========

A Jupyter Spawner hook for creating LDAP DIT entries via `pre_spawn_hook
<https://jupyterhub.readthedocs.io/en/stable/api/spawner.html?highlight=pre_spawn_hook>`_

------------
Installation
------------

Installation from pypi::

    pip install ldap-hooks

Installation from local git repository::

    cd ldap_hooks
    pip install .

-------------
Configuration
-------------

You should edit your ``jupyterhub_config.py`` config file to set a particular
pre_spawn_hook, E.g::

    from ldap_hooks import hello_hook

    c.Spawner.pre_spawn_hook = hello_hook

Beyond this, a set of connection parameters must be set in order for
the JupyterHub server to be able to interact with the designated LDAP host::

    from ldap_hooks import LDAP

    LDAP.url = "openldap"
    LDAP.user = "cn=admin,dc=example,dc=org"
    LDAP.password = "dummyldap_password"
    LDAP.base_dn = "dc=example,dc=org"

The user's permissions here depend on whether the hook is just
extracting information, or is creating entries as well.

The hooks that this library provides can be found below.

By default, any of these hooks are called by the Spawner
with the following syntax::

    def hook(spawner):
        # Do stuff inside the hook
        return True

That is, the hook expects that the current ``spawner`` instance
is passed to it, which it can subsequently use to access
properties of it, such as the ``user`` instance.

=====================
setup_ldap_entry_hook
=====================

This hook enables that the Spawner will submit/create an LDAP entry
before the spawner starts the notebook. It is activate by setting the
following parameter in the JupyterHub config::

    from ldap_hooks import setup_ldap_entry_hook

    c.Spawner.pre_spawn_hook = setup_ldap_entry_hook

In addition, the hook requires a number of a parameters to be configured
before it will work as intended.

-------------------
Basic Configuration
-------------------

First, to defined the following options, the ``LDAP`` class
must be imported into the ``jupyterhub_config.py`` file::

    from ldap_hooks import LDAP

With this completed, the `submit_spawner_attribute` must be set,
this must point to the variable path in the spawner instance
where it can find the `Distinguished Name String (DN) <https://ldapwiki.com/wiki/Distinguished%20Names>`_ value.
This string value makes up the entry that is to be submitted to the LDAP DIT,
E.g::

    # Retrieve the Distinguished Name from the 'spawner.user.data' variable
    LDAP.submit_spawner_attribute = 'user.data'

In addition if this variable is of a dictionary structure,
a tuple row can be specified to define the set of keys that
should be used to extract the Distinguished Name value.
For instance, if the value is in the
spawner.user.data['User']['DN'] structure::

    # Extract the Distinguished Name string from the
    # spawner.user.data['User']['DN'] path.
    LDAP.submit_spawner_attribute = 'user.data'
    LDAP.submit_spawner_attribute_keys = ('User', 'DN')

If this extracted string is formatted in a way that is
incorrectly seperated, the ``replace_object_with`` parameter can be
used to fix this, E.g.::

    # Prepare LDAP DN object entry
    LDAP.replace_object_with = {'/': '+'}
    # Does the following replacement
    # /telephoneNumber=23012303403/SN=My Surname/CN=a-new-user
    # +telephoneNumber=23012303403+SN=My Surname+CN=a-new-user

By default the ``name_strip_chars`` parameter is
defined to strip extra characters that are either
pre or postfixed to the DN::

    # Default value
    LDAP.name_strip_chars = ['/', '+', '*', ',', '.', '!', ' ']

Which means that it will automatically strip
the prefixed ``+`` from the ``replace_object_with`` output.

Before the hook can submit the prepared DN,
it first has to know which `Structural ObjectClass <https://ldapwiki.com/wiki/STRUCTURAL>`_
should be used to create the entry with.
Beyond at least one required Structural ObjectClass,
a list of additional `Auxiliary ObjectClasses <https://ldapwiki.com/wiki/AUXILIARY>`_
can be specified as well.
All of which must be set via the ``object_classes`` parameter, E.g::

    # Structural 'Person'
    LDAP.object_classes = ['Person']

Any specified object class must be supported as
part of the specified ``LDAP.url`` server schema.

Beyond the ``object_classes``, the hook also
provides a parameter to specify additional object
attributes to submittet DN entry::

    LDAP.object_attributes = {'description': 'A default person account',
                              'surname': 'MySurname'}

Duplicate entries can be default not exist in the LDAP DIT,
therefore any duplicate DN submission will fail.
By default the hook will search the DIT for
an entry that matches every attribute of the DN string,
if such an entry exists, the hook will simply stop before
attempting to submit it. This behaviour can be customised
via the ``unique_object_attributes`` parameter as shown in
the "Extra Features" section.


--------------
Extra Features
--------------

^^^^^^^^^^^^^^^^^^^^^^^^
unique_object_attributes
^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to specify special attributes
that the hook should use for this search via
the ``unique_object_attributes`` parameter::

    # Optional parameter
    LDAP.unique_object_attributes = ['surname']

Now the hook will search for if an entry with ``object_classes``
exists, if so it will stop the submission.

^^^^^^^^^^^^^^^^^^^^^^
set_spawner_attributes
^^^^^^^^^^^^^^^^^^^^^^

Use this to set JupyterHub Spawner attributes.
For instance set an environment variable of the Spawned notebooks::

    # Set Spawned Notebook environment vars
    LDAP.set_spawner_attributes = {
        'environment': {'ENV_VAR': 'Hello from LDAP Hook'}
    }

^^^^^^^^^^^^^^^^^^^^^^^^
search_attribute_queries
^^^^^^^^^^^^^^^^^^^^^^^^

Use this to define a list of LDAP search operations to extract a
list of attributes from the existing DIT which can subsequntly be used
to perform some subsequent operation on the extracted attributes,
or share them with the ``set_spawner_attributes`` or ``object_attributes``
via the ``dynamic_attributes`` definition.

For instance, extract the ``uidNumber`` attribute from the LDAP DIT
which has the ``x-nextUserIdentifier`` objectclass::

    LDAP.search_attribute_queries = [
        {'search_base': LDAP.base_dn,
        'search_filter': '(objectclass=X-nextUserIdentifier)',
        'attributes': ['uidNumber']}
    ]

^^^^^^^^^^^^^^^^^^^^^^^^
search_result_operations
^^^^^^^^^^^^^^^^^^^^^^^^

Use this to perform an operation action on extracted attributes of the
``search_attribute_queries``. The specific action must be defined
as a LDAP.SEARCH_RESULT_OPERATION_ACTIONS.
For instance, increment the value of the extracted ``uidNumber`` attribute by 1,
for this particular action, it is required that the ``modify_dn`` key is also
provided since it defines the Distinguished Name that should be used to select that attribute to be incremented in the DIT::

    modify_dn = 'cn=uidNumber' + ',' + LDAP.base_dn
    LDAP.search_result_operation = {'uidNumber': {'action': INCREMENT_ATTRIBUTE,
                                                'modify_dn': modify_dn}}

This will produce an atomic modify-increment to the value of the ``cn=uidNumber,dc=example,dc=org``.

^^^^^^^^^^^^^^^^^^
dynamic_attributes
^^^^^^^^^^^^^^^^^^

To format ``set_spawner_attributes`` and ``object_attributes`` with dynamic attributes,
such as the result of an LDAP.SEARCH_RESULT_OPERATION_ACTIONS or values provided
by a ``submit_spawner_attribute`` dictionary. The ``dynamic_attributes`` can
be used to format such attributes. For instance, if the ``set_spawner_attributes``
defines attributes that expects formatting of the 'emailAddress' and 'uidNumber'::

    LDAP.set_spawner_attributes = {
        'environment': {'NB_USER': '{emailAddress}',
                        'NB_UID': '{uidNumber}'},
    }

The ``dynamic_attributes`` can provide these as follows::

    LDAP.dynamic_attributes = {
        'emailAddress': SPAWNER_SUBMIT_DATA,
        'uidNumber': LDAP_SEARCH_ATTRIBUTE_QUERY
    }

Where the values of the keys define how and where the attribute values should be extracted.
The specified value must be defined as a LDAP.DYNAMIC_ATTRIBUTE_METHODS.

In addition these ``dynamic_attributes`` are made available to the defined ``object_attributes``.
For example::

    LDAP.object_attributes = {'uidNumber': '{uidNumber}',
                              'homeDirectory': '/home/{emailAddress}'}

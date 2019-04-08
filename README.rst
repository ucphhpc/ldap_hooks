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

---------------------
setup_ldap_entry_hook
---------------------

This hook enables that the Spawner will submit/create an LDAP entry
before the spawner starts the notebook. It is activate by setting the
following parameter in the JupyterHub config::

    from ldap_hooks import setup_ldap_entry_hook

    c.Spawner.pre_spawn_hook = setup_ldap_entry_hook

In addition, the hook requires a number of a parameters to be configured
before it will work as intended.

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
    # /C=NA/ST=NA/L=NA/O=NA/OU=NA/CN=User Name/emailAddress=email@address.com
    # +C=NA+ST=NA+L=NA+O=NA+OU=NA+CN=User Name+emailAddress=email@address.com

By default the ``name_strip_chars`` parameter is
defined to strip extra characters that are either
pre or postfixed to the DN::

    # Default value
    LDAP.name_strip_chars = ['/', '+', '*', ',', '.', '!', ' ']

Which means that it will automatically strip
the prefixed ``+`` from ``replace_object_with`` output.

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


Extra Features
--------------

It is also possible to specify special attributes
that the hook should use for this search via
the ``unique_object_attributes`` parameter::

    # Optional parameter
    LDAP.unique_object_attributes = ['surname']

Now the hook will search for if an entry with ``object_classes``
exists, if so it will stop the submission.

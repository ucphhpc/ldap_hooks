import logging
import copy
from tornado import gen
from ldap3 import Server, Connection, MODIFY_DELETE, MODIFY_ADD, BASE, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException
from ldap3.utils.log import set_library_log_detail_level, BASIC
from traitlets import Unicode, Dict, List, Tuple
from traitlets.config import LoggingConfigurable
from textwrap import dedent
from .ldap import add_dn, search_for, modify_dn
from .utils import recursive_format


SPAWNER_SUBMIT_DATA = "1"
LDAP_SEARCH_ATTRIBUTE_QUERY = "2"
SPAWNER_ATTRIBUTE = "3"
SPAWNER_USER_ATTRIBUTE = "4"
LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY = "5"

DYNAMIC_ATTRIBUTE_METHODS = (
    SPAWNER_SUBMIT_DATA,
    LDAP_SEARCH_ATTRIBUTE_QUERY,
    SPAWNER_ATTRIBUTE,
    SPAWNER_USER_ATTRIBUTE,
    LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY,
)
INCREMENT_ATTRIBUTE = "1"
SEARCH_RESULT_OPERATION_ACTIONS = (INCREMENT_ATTRIBUTE,)


class LDAP(LoggingConfigurable):

    url = Unicode(
        allow_none=False,
        config=True,
        help=dedent(
            """
    URL/IP of the LDAP server. E.g. 127.0.0.1
    """
        ),
    )

    user = Unicode(
        allow_none=False,
        config=True,
        help=dedent(
            """
    Distinguished Name String that is used to connect to the LDAP server.
    E.g. cn=admin,dc=example,dc=org
    """
        ),
    )

    password = Unicode(
        allow_none=True,
        config=True,
        help=dedent(
            """
    Password used to authenticate as user.
    """
        ),
    )

    ssl_cert_path = Unicode(
        allow_none=True,
        config=True,
        help=dedent(
            """
    A path to the SSL certificate that is used to authenticate
    as the 'user' with.
    """
        ),
    )

    base_dn = Unicode(
        allow_none=False,
        config=True,
        help=dedent(
            """
    """
        ),
    )

    object_classes = List(
        trait=Unicode(),
        default_value=[],
        allow_none=False,
        config=True,
        help=dedent(
            """
    Which LDAP object classes should be used for the add operation.
    """
        ),
    )

    object_attributes = Dict(
        value_trait=Unicode(),
        key_trait=Unicode(),
        default_value={},
        help=dedent(
            """
    Which attributes should be attached to a specified LDAP object_class.
    """
        ),
    )

    unique_object_attributes = List(
        trait=Unicode(),
        default_value=[],
        help=dedent(
            """
    List of attributes inside the defined object_classes which are unique
    and can't have duplicates in the DIT with the same object classes.
    """
        ),
    )

    replace_object_with = Dict(
        value_trait=Unicode(),
        key_trait=Unicode(),
        default_value={},
        help=dedent(
            """
    A dictionary of key value pairs that should be used to prepare the submit
    object string.

    E.g. {'/': '+'}
    Which translates the following distinguished name as:
        /C=NA/ST=NA/L=NA/O=NA/OU=NA/CN=User Name/emailAddress=email@address.com

        +C=NA+ST=NA+L=NA+O=NA+OU=NA+CN=User Name+emailAddress=email@address.com
    """
        ),
    )

    name_strip_chars = List(
        trait=Unicode(),
        default_value=["/", "+", "*", ",", ".", "!", " "],
        help=dedent(
            """
    A list of characters that should be lstriped and rstriped from
    the submit name.
    """
        ),
    )

    submit_spawner_attribute = Unicode(
        allow_none=False,
        config=True,
        default_value=None,
        help=dedent(
            """
    A . seperated string that contains the property path to access
    the LDAP object string in the passed in spawner object.

    The resulting attribute can subsequently be prepared by
    submit_spawner_attribute_keys lookup, if the attribute contains
    a dictionary.

    The final extracted submit value is subsequently processed
     by replace_object_with before it is submitted to the LDAP DIT.
    E.g:
        'user.data.ldap_object_distinguish_name_string_or_dict'
    """
        ),
    )

    submit_spawner_attribute_keys = Tuple(
        allow_none=True,
        config=True,
        default_value=(),
        help=dedent(
            """
    A tuple containing the key's lookup path to extract the
    submit value from the identified dictionary as defined by
    submit_spawner_attribute.

    E.g:
        ('ldap_object_dict_key',)
    """
        ),
    )

    dynamic_attributes = Dict(
        value_trait=Unicode(),
        key_trait=Unicode(),
        default_value={},
        help=dedent(
            """
    A dict of dynamic attributes that is generated from one of
    DYNAMIC_ATTRIBUTE_METHODS methods to extract values.
    """
        ),
    )

    search_attribute_queries = List(
        trait=Dict(),
        default_value=[],
        help=dedent(
            """
    A list of expected variables to be extracted and prepared
    from the base_dn LDAP DIT before creation
    """
        ),
    )

    search_result_operations = Dict(
        value_trait=Dict(),
        key_trait=Unicode(),
        default_value={},
        help=dedent(
            """
    A dict of attribute operations that should be carried out after
    search_attribute_queries has been retrived. The 'action' key value
    must be defined in SEARCH_RESULT_OPERATION_ACTIONS.
    E.g.
        {'uidNumber': {'action': INCREMENT_ATTRIBUTE,
                       'modify_dn': 'cn=uidNext,dc=example,dc=org'}}
    """
        ),
    )

    set_spawner_attributes = Dict(
        value_trait=Unicode(),
        key_trait=Unicode(),
        default_value={},
        help=dedent(
            """
    A dict of attributes that should be set on the passed in spawner object.
    """
        ),
    )


class ConnectionManager:
    def __init__(self, url, logger=None, **connection_args):
        if url is None:
            raise TypeError("url argument must be provided")

        if not isinstance(url, str) or not url:
            raise ValueError("url must be a non zero length string")

        if connection_args and not isinstance(connection_args, dict):
            raise TypeError("con    nection_args must be a dictionary")

        self.url = url
        self.logger = logger
        self.connection_args = connection_args
        self.connection = None
        self.connected = False

    def connect(self, **kwargs):
        server = Server(self.url, **kwargs)
        try:
            if self.connection_args:
                # Can be Anonymous if both 'user' and 'password' are None
                self.connection = Connection(server, **self.connection_args)
            else:
                # Anonymous login
                self.connection = Connection(server)
        except LDAPException as err:
            self.connected = False
            if (
                self.logger is not None
                and getattr(self.logger, "error", None)
                and callable(self.logger.error)
            ):
                self.logger.error(
                    "LDAP - Failed to create a connection, " "exception: {}".format(err)
                )
            return None

        try:
            self.connected = self.connection.bind()
            if not self.connected:
                if (
                    self.logger is not None
                    and getattr(self.logger, "error", None)
                    and callable(self.logger.error)
                ):
                    self.logger.error(
                        "LDAP - bind executed without error, "
                        "but bind still failed: {}".format(self.connected)
                    )
        except LDAPException as err:
            self.connected = False
            if (
                self.logger is not None
                and getattr(self.logger, "error", None)
                and callable(self.logger.error)
            ):
                self.logger.error(
                    "LDAP - Failed to bind connection, " "exception: {}".format(err)
                )
            return None

    def is_connected(self):
        return self.connected

    def get_connection(self):
        return self.connection

    def change_connection_user(self, **user_args):
        try:
            self.connection = self.connection.rebind(user_args)
        except LDAPException as err:
            if (
                self.logger is not None
                and getattr(self.logger, "error", None)
                and callable(self.logger.error)
            ):
                self.logger.error(
                    "LDAP - Failed to rebind connection, " "exception: {}".format(err)
                )

    def disconnect(self):
        if self.connection.unbind():
            self.connected = False

    def get_response(self):
        return self.connection.response

    def get_response_attributes(self):
        entry_attributes = {}
        resp = self.get_response()
        if not resp:
            return None

        dn = None
        for entry in resp:
            if not dn:
                dn = entry["dn"]
            if "attributes" in entry:
                # Multiple dn's, fail
                if dn != entry["dn"]:
                    return None
                entry_attributes.update({entry["dn"]: entry["attributes"]})
        return entry_attributes[dn]

    def get_result(self):
        return self.connection.result


def get_dict_key(input_dict, attr):
    if attr not in input_dict:
        return None
    return input_dict[attr]


def get_attr(obj, attr):
    has_attr = hasattr(obj, attr)
    if not has_attr:
        return False
    return getattr(obj, attr)


def rec_get_attr(obj, attr):
    attributes = attr.split(".")
    for attr in attributes:
        obj = get_attr(obj, attr)
        if not obj:
            return False
    return obj


def tuple_dict_select(select_tuple, select_dict):
    selected = {}
    for key in select_tuple:
        if selected and isinstance(selected, dict) and key in selected:
            selected = selected[key]
        else:
            selected = select_dict[key]
    return selected


def perform_search_result_operation(
    logger, conn_manager, base_dn, operation, attr_key, attr_val
):
    logger.debug(
        "LDAP - enter perform_search_result_operation, "
        "{}-{}-{}".format(operation, attr_key, attr_val)
    )
    if "action" not in operation:
        logger.error("LDAP - missing action key in: {}".format(operation))
        return False

    if operation["action"] not in SEARCH_RESULT_OPERATION_ACTIONS:
        logger.error(
            "LDAP - Illegal search_result_operation: {}"
            " must be one of: {}".format(
                operation["action"], SEARCH_RESULT_OPERATION_ACTIONS
            )
        )
        return False
    return_value = None
    if operation["action"] == INCREMENT_ATTRIBUTE:
        valid_types = (int, float)
        if not isinstance(attr_val, valid_types):
            logger.error(
                "LDAP - Invalid datatype: {} supplied to "
                "operation: {}, allowed are: {}".format(
                    type(attr_val), INCREMENT_ATTRIBUTE, valid_types
                )
            )
            return False
        if "modify_dn" not in operation:
            logger.error(
                "LDAP - Missing required modify_dn key in: {}".format(operation)
            )
            return False
        return_value = attr_val + 1

        # Atomic increment
        dn = operation["modify_dn"]
        success = modify_dn(
            conn_manager.get_connection(),
            dn,
            {attr_key: [(MODIFY_DELETE, [attr_val]), (MODIFY_ADD, [return_value])]},
        )
        if not success:
            logger.error(
                "LDAP - failed to increment attr_key: {} "
                "in LDAP DIT with: {}".format(attr_key, dn)
            )
            return False

    return return_value


def get_interpolated_dynamic_attributes(logger, sources, dynamic_attributes):
    return_dict = {}
    for attr_key, attr_val in dynamic_attributes.items():
        val = None
        if attr_val not in DYNAMIC_ATTRIBUTE_METHODS:
            logger.error(
                "LDAP - Illegal dynamic_attributes value: {}"
                " must be one of: {}".format(attr_val, DYNAMIC_ATTRIBUTE_METHODS)
            )
            return False

        if attr_val == LDAP_SEARCH_ATTRIBUTE_QUERY:
            if (
                LDAP_SEARCH_ATTRIBUTE_QUERY in sources
                and sources[LDAP_SEARCH_ATTRIBUTE_QUERY]
            ):
                val = get_dict_key(sources[LDAP_SEARCH_ATTRIBUTE_QUERY], attr_key)
        if attr_val == LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY:
            if (
                LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY in sources
                and sources[LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY]
            ):
                val = get_dict_key(sources[LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY], attr_key)
                if isinstance(val, (list, set, tuple)):
                    val = val[0]

        if attr_val == SPAWNER_SUBMIT_DATA:
            if SPAWNER_SUBMIT_DATA in sources and sources[SPAWNER_SUBMIT_DATA]:
                val = get_dict_key(sources[SPAWNER_SUBMIT_DATA], attr_key)
        if attr_val == SPAWNER_ATTRIBUTE:
            if SPAWNER_ATTRIBUTE in sources and sources[SPAWNER_ATTRIBUTE]:
                val = get_attr(sources[SPAWNER_ATTRIBUTE], attr_key)
        if attr_val == SPAWNER_USER_ATTRIBUTE:
            if SPAWNER_USER_ATTRIBUTE in sources and sources[SPAWNER_USER_ATTRIBUTE]:
                val = get_attr(sources[SPAWNER_USER_ATTRIBUTE], attr_key)
        if val:
            return_dict[attr_key] = val
    logger.debug("LDAP - prepared interpolated_attributes {}".format(return_dict))
    return return_dict


def update_spawner_attributes(spawner, spawner_attributes):
    for spawner_attr, spawner_value in spawner_attributes.items():
        if hasattr(spawner, spawner_attr):
            attr = getattr(spawner, spawner_attr)
            if isinstance(attr, dict):
                attr.update(spawner_value)
            if isinstance(attr, (list, set, tuple, str)):
                setattr(spawner, spawner_attr, spawner_value)
        else:
            setattr(spawner, spawner_attr, spawner_value)


@gen.coroutine
def hello_hook(spawner):
    spawner.log.info("Hello from hook")
    return True


@gen.coroutine
def setup_ldap_entry_hook(spawner):
    instance = LDAP()
    # TODO, copy entire default config options dynamically
    instance.dynamic_attributes = copy.deepcopy(instance.dynamic_attributes)
    instance.set_spawner_attributes = copy.deepcopy(instance.set_spawner_attributes)
    instance.object_attributes = copy.deepcopy(instance.object_attributes)
    instance.search_result_operations = copy.deepcopy(instance.search_result_operations)

    logging.basicConfig(filename="client_application.log", level=logging.DEBUG)
    set_library_log_detail_level(BASIC)

    if not instance.submit_spawner_attribute:
        spawner.log.error(
            "LDAP - either submit_spawner_attribute "
            "has to define the object which is to be submitted to the LDAP DIT"
        )
        return False

    ldap_data = rec_get_attr(spawner, instance.submit_spawner_attribute)
    if not ldap_data:
        spawner.log.error(
            "LDAP - The spawner object: {} did not have "
            "the specified attribute: {}".format(
                spawner.user.__dict__, instance.submit_spawner_attribute
            )
        )
        return False

    if isinstance(ldap_data, dict):
        if not instance.submit_spawner_attribute_keys:
            spawner.log.error(
                "LDAP - Found attribute: {} in spawner object: "
                "{}, of type: {}, requires that submit_spawner"
                "_attribute_keys is set to extract the value "
                "from the dictionary".format(
                    instance.submit_spawner_attribute, spawner, type(ldap_data)
                )
            )
            return False

        if not isinstance(instance.submit_spawner_attribute_keys, tuple):
            spawner.log.error(
                "LDAP - submit_spawner_attribute_keys is "
                "of incorrect type: {} must be a tuple".format(
                    type(instance.submit_spawner_attribute_keys)
                )
            )
            return False

        new_ldap_data = tuple_dict_select(
            instance.submit_spawner_attribute_keys, ldap_data
        )
        if not new_ldap_data:
            spawner.log.error(
                "LDAP - Failed to extract the specified dict "
                "tuple string: {} from dict: {}".format(
                    instance.submit_spawner_attribute_keys, ldap_data
                )
            )
            return False

        ldap_data = new_ldap_data
        if not isinstance(ldap_data, str):
            spawner.log.error(
                "LDAP - {} is of incorrect type, requires: {} "
                "found: {}".format(ldap_data, str, type(ldap_data))
            )
            return False

    # Parse spawner user LDAP string to be parsed for submission
    conn_manager = ConnectionManager(
        instance.url, logger=spawner.log, user=instance.user, password=instance.password
    )
    conn_manager.connect()

    entry = None
    if conn_manager.is_connected():
        # Check objectclasses support
        success = search_for(
            conn_manager.get_connection(),
            "cn=Subschema",
            "(objectClass=Subschema)",
            search_scope=BASE,
            attributes=["objectClasses"],
        )
        response = conn_manager.get_response()
        if not success:
            spawner.log.error(
                "LDAP - failed to query for "
                "supported objectClasses {}".format(response)
            )
            return False

        spawner.log.debug("LDAP - supported objectClasses {}".format(response))
        found = []
        for entry in response:
            object_classes = entry["attributes"]["objectClasses"]
            found = [
                req_obj_class
                for obj_class in object_classes
                for req_obj_class in instance.object_classes
                if req_obj_class.lower() in obj_class.lower()
            ]

        missing = set(instance.object_classes) - set(found)
        if missing:
            spawner.log.error(
                "LDAP - only found: {} required "
                "supported objectclasses, missing: {}".format(found, missing)
            )
            return False

        # Prepare ldap data
        spawner.log.info("LDAP - Submit data {}".format(ldap_data))
        spawner.log.info(
            "LDAP - replace_object_with {}".format(instance.replace_object_with)
        )

        for replace_key, replace_val in instance.replace_object_with.items():
            ldap_data = ldap_data.replace(replace_key, replace_val)

        for strip in instance.name_strip_chars:
            ldap_data = ldap_data.strip(strip)

        # Turn ldap data string into dict, split on =
        ldap_dict = {}
        for replace_key, replace_val in instance.replace_object_with.items():
            ldap_dict.update(
                dict(item.split("=") for item in ldap_data.split(replace_val))
            )

        spawner.log.info(
            "LDAP - Prepared dn: {} for submission and dict: {} "
            "for attribute setup".format(ldap_data, ldap_dict)
        )

        # LDAP, check for unique attributes that should not be duplicated

        search_filter = ""
        # objectclasses search filter
        if instance.object_classes:
            search_filter = "(&{})".format(
                "".join(
                    [
                        "(objectclass={})".format(object_class)
                        for object_class in instance.object_classes
                    ]
                )
            )

        if instance.unique_object_attributes:
            # Specific attributes to check for existing dn
            search_attributes = "".join(
                [
                    "({}={})".format(attr.lower(), ldap_dict[attr])
                    for attr in instance.unique_object_attributes
                    if attr in ldap_dict
                ]
            )
        else:
            # Use every attribute to check for existing dn
            search_attributes = "".join(
                [
                    "({}={})".format(ldap_key, ldap_value)
                    for ldap_key, ldap_value in ldap_dict.items()
                ]
            )

        # unique attributes search filter
        if search_filter:
            # strip last )
            search_filter = search_filter[:-1]
            search_filter += search_attributes + ")"
        else:
            search_filter = "(&{})".format(search_attributes)

        spawner.log.debug(
            "LDAP - unique_check, search_filter: {}".format(search_filter)
        )
        # Check whether dn already exists
        success = search_for(
            conn_manager.get_connection(),
            instance.base_dn,
            search_filter,
            attributes=ALL_ATTRIBUTES,
        )
        if success:
            spawner.log.info(
                "LDAP - {} already exist, response {}".format(
                    ldap_dict, conn_manager.get_response()
                )
            )

            response = conn_manager.get_response()
            if len(response) > 1:
                spawner.log.error(
                    "LDAP - multiple entries: {} "
                    "were found with: {}".format(response, search_filter)
                )
                return False

            attributes = conn_manager.get_response_attributes()
            if not attributes:
                spawner.log.error(
                    "LDAP - No attributes were returned from "
                    "existing dn: {} "
                    "with search_filer: {}".format(ldap_data, search_filter)
                )
                return False

            spawner.log.info("LDAP - Retrived attributes {}".format(attributes))
            # Extract attributes from existing object
            sources = {
                LDAP_SEARCH_ATTRIBUTE_QUERY: attributes,
                LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY: attributes,
                SPAWNER_SUBMIT_DATA: ldap_dict,
                SPAWNER_ATTRIBUTE: spawner,
                SPAWNER_USER_ATTRIBUTE: spawner.user,
            }
            spawner.log.debug(
                "LDAP - dynamic_attributes "
                "pre interpolated: {}".format(instance.dynamic_attributes)
            )
            prepared_dynamic_attributes = get_interpolated_dynamic_attributes(
                spawner.log, sources, instance.dynamic_attributes
            )

            if instance.dynamic_attributes and not prepared_dynamic_attributes:
                spawner.log.error(
                    "LDAP - Failed to setup prepared_attributes:"
                    " {} with attribute_dict: {}".format(
                        prepared_dynamic_attributes, attributes
                    )
                )
                return False
            spawner.log.debug(
                "LDAP - dynamic_attributes "
                "post interpolated: {}".format(prepared_dynamic_attributes)
            )
            # Setup set_spawner_attributes
            recursive_format(
                instance.set_spawner_attributes, prepared_dynamic_attributes
            )
            update_spawner_attributes(spawner, instance.set_spawner_attributes)
            return True

        # Create new DIT entry
        # Get extract variables
        sources = {}
        for q in instance.search_attribute_queries:
            query = copy.deepcopy(q)
            spawner.log.debug("LDAP - extract search_attribute_query: {}".format(query))
            if "search_base" not in query or "search_filter" not in query:
                spawner.log.error(
                    "LDAP - search_base or search_filter "
                    "is missing from search_attribute_queries: "
                    "{}".format(query)
                )
                return False
            success = search_for(
                conn_manager.get_connection(),
                query.pop("search_base", ""),
                query.pop("search_filter", ""),
                **query
            )
            if not success:
                spawner.log.error(
                    "LDAP - failed to use the query: {} "
                    "for extracting attributes, response was:"
                    "{}".format(query, conn_manager.get_response())
                )
                return False

            # get responses
            response = conn_manager.get_response()
            if len(response) > 1:
                spawner.log.error(
                    "LDAP - multiple entries: {} "
                    "were found with: {}".format(response, search_filter)
                )
                return False

            attributes = conn_manager.get_response_attributes()
            spawner.log.debug(
                "LDAP - search_attribute_queries " "attributes: {}".format(attributes)
            )
            if attributes:
                # Perform search_result_operations
                for attr_key, attr_val in attributes.items():
                    if attr_key in instance.search_result_operations:
                        post_operation_val = perform_search_result_operation(
                            spawner.log,
                            conn_manager,
                            instance.base_dn,
                            instance.search_result_operations[attr_key],
                            attr_key,
                            attr_val,
                        )
                        if not post_operation_val:
                            spawner.log.error(
                                "LDAP - Failed to get "
                                "a valid result from "
                                "perform_search_result_operation"
                            )
                            return False
                        attributes[attr_key] = post_operation_val
                        sources.update(
                            {
                                LDAP_SEARCH_ATTRIBUTE_QUERY: {
                                    attr_key: post_operation_val
                                },
                                LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY: {
                                    attr_key: post_operation_val
                                },
                            }
                        )

                ldap_dict.update(attributes)

        # Prepare required dynamic attributes
        sources.update(
            {
                SPAWNER_SUBMIT_DATA: ldap_dict,
                SPAWNER_ATTRIBUTE: spawner,
                SPAWNER_USER_ATTRIBUTE: spawner.user,
            }
        )
        spawner.log.debug(
            "LDAP - Sources state before interpolation "
            "with dynamic attributes {}".format(sources)
        )

        prepared_object_attributes = get_interpolated_dynamic_attributes(
            spawner.log, sources, instance.dynamic_attributes
        )

        spawner.log.debug(
            "LDAP - prepared_object_attributes:"
            " {}".format(prepared_object_attributes)
        )

        if instance.dynamic_attributes and not prepared_object_attributes:
            spawner.log.error(
                "LDAP - Failed to setup "
                "prepared_object_attributes: {} with "
                "attribute_dict: {}".format(prepared_object_attributes, ldap_dict)
            )
            return False

        # Format dn provided variables
        recursive_format(instance.object_attributes, prepared_object_attributes)
        spawner.log.debug(
            "LDAP - prepared object attributes {}".format(instance.object_attributes)
        )

        # Add DN
        spawner.log.info(
            "LDAP - submit object: {}, attributes: {} "
            "dn: {}".format(
                instance.object_classes, instance.object_attributes, ldap_data
            )
        )
        success = add_dn(
            conn_manager.get_connection(),
            ",".join([ldap_data, instance.base_dn]),
            object_class=instance.object_classes,
            attributes=instance.object_attributes,
        )
        if not success:
            result = conn_manager.get_result()
            spawner.log.error(
                "LDAP - Failed to add {} to {} err: {}".format(
                    ldap_data, instance.url, result
                )
            )
            # If web enabled render result
            return False

        spawner.log.info(
            "LDAP - User: {} created: {} "
            "at: {} with response: {}".format(
                spawner.user.name, ldap_data, instance.url, conn_manager.get_response()
            )
        )
        # Check that it exists in the db
        search_base = instance.base_dn
        search_filter = "(&{}".format(
            "".join(
                [
                    "(objectclass={})".format(object_class)
                    for object_class in instance.object_classes
                ]
            )
        )

        search_filter += "{})".format(
            "".join(
                [
                    "({}={})".format(attr_key, attr_val)
                    for attr_key, attr_val in instance.object_attributes.items()
                ]
            )
        )
        spawner.log.debug(
            "LDAP - search_for, "
            "search_base {}, search_filter {}".format(search_base, search_filter)
        )
        success = search_for(
            conn_manager.get_connection(),
            search_base,
            search_filter,
            attributes=ALL_ATTRIBUTES,
        )
        if not success:
            spawner.log.error(
                "Failed to find {} at {}".format(
                    (search_base, search_filter), instance.url
                )
            )
            return False
        spawner.log.info(
            "LDAP - found {} in {}".format(conn_manager.get_response(), instance.url)
        )

        response = conn_manager.get_response()
        if len(response) > 1:
            spawner.log.error(
                "LDAP - multiple entries: {} were found with:"
                " {}".format(response, search_filter)
            )
            return False

        attributes = conn_manager.get_response_attributes()
        # TODO, validate all the attributes are as expected
        if not attributes:
            spawner.log.error(
                "LDAP - No attributes were returned from "
                "existing dn: {} with search_filer: {}".format(ldap_data, search_filter)
            )
            return False

        sources.update(
            {
                LDAP_SEARCH_ATTRIBUTE_QUERY: attributes,
                LDAP_FIRST_SEARCH_ATTRIBUTE_QUERY: attributes,
            }
        )
        prepared_spawner_attributes = get_interpolated_dynamic_attributes(
            spawner.log, sources, instance.dynamic_attributes
        )

        recursive_format(instance.set_spawner_attributes, prepared_spawner_attributes)
        spawner.log.debug(
            "LDAP - formatted set_spawner_attributes: "
            "{} for the new entry: {}".format(
                instance.set_spawner_attributes, attributes
            )
        )
        # Pass prepared attributes to spawner attributes
        update_spawner_attributes(spawner, instance.set_spawner_attributes)
        return True
    else:
        spawner.log.error("LDAP - Failed to connect to {}".format(instance.url))
        return False

    return None

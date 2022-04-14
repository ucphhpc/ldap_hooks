import docker
import os
import requests
import logging
import pytest
from urllib.parse import urljoin
from ldap3 import ALL_ATTRIBUTES
from ldap_hooks import search_for, ConnectionManager
from os.path import join, dirname, realpath
from docker.types import Mount
from .util import (
    wait_for_site,
    get_container,
    get_container_env,
    get_container_user,
    delete,
    wait_for_container,
)

# root dir
docker_path = dirname(dirname(realpath(__file__)))

# Logger
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger()

JHUB_IMAGE_NAME = "jupyterhub-ldap-hooks"
JHUB_IMAGE_TAG = "test"
JHUB_IMAGE = "".join([JHUB_IMAGE_NAME, ":", JHUB_IMAGE_TAG])
PORT = 8000

jhub_image_spec = {"path": docker_path, "tag": JHUB_IMAGE, "rm": "True", "pull": "True"}

LDAP_IMAGE_PATH = "osixia/openldap"
LDAP_IMAGE_NAME = "openldap"
LDAP_IMAGE_TAG = "1.2.3"
LDAP_IMAGE = "".join([LDAP_IMAGE_PATH, ":", LDAP_IMAGE_TAG])

JHUB_URL = "http://127.0.0.1:{}".format(PORT)

LDAP_URL = "http://openldap"

# Config setup
config_path = join(dirname(realpath(__file__)), "configs")

jhub_config_path = join(config_path, "jhub", "ldap_person_hook.py")
jhub_target_config = os.path.join(os.sep, "etc", "jupyterhub", "jupyterhub_config.py")

ldap_schema = join(config_path, "openldap", "mount_schema")
ldap_target_schema = "/container/service/slapd/assets/config/bootstrap/schema"

ldap_servers = join(config_path, "openldap", "openldap-servers")
ldap_target_servers = "/opt/openldap-servers"

LDAP_NETWORK_NAME = "jhub_ldap_network"
ldap_network_config = {
    "name": LDAP_NETWORK_NAME,
    "driver": "bridge",
    "attachable": True,
}

docker_mount = Mount(
    source=os.path.join(os.sep, "var", "run", "docker.sock"),
    target=os.path.join(os.sep, "var", "run", "docker.sock"),
    read_only=True,
    type="bind",
)

# container cmd
jhub_cont = {
    "image": JHUB_IMAGE,
    "name": JHUB_IMAGE_NAME,
    "mounts": [
        Mount(
            source=jhub_config_path,
            target=jhub_target_config,
            read_only=True,
            type="bind",
        ),
        docker_mount,
    ],
    "ports": {PORT: PORT},
    "network": LDAP_NETWORK_NAME,
    "detach": "True",
    "command": "jupyterhub --debug -f " + jhub_target_config,
}

LDAP_DOMAIN = "example.org"
LDAP_USER = "cn=admin,dc=example,dc=org"
LDAP_PASSWORD = "dummyldap_password"

ldap_cont = {
    "image": LDAP_IMAGE,
    "name": LDAP_IMAGE_NAME,
    "mounts": [
        Mount(
            source=ldap_schema, target=ldap_target_schema, read_only=False, type="bind"
        ),
        Mount(
            source=ldap_servers,
            target=ldap_target_servers,
            read_only=False,
            type="bind",
        ),
    ],
    "ports": {389: 389, 636: 636},
    "network": LDAP_NETWORK_NAME,
    "detach": "True",
    "environment": {
        "LDAP_DOMAIN": LDAP_DOMAIN,
        "LDAP_ADMIN_PASSWORD": LDAP_PASSWORD,
        "LDAP_CONFIG_PASSWORD": LDAP_PASSWORD,
        "LDAP_RFC2307BIS_SCHEMA": "true",
    },
    "command": "--copy-service",
}


@pytest.mark.parametrize("build_image", [jhub_image_spec], indirect=["build_image"])
@pytest.mark.parametrize("network", [ldap_network_config], indirect=["network"])
@pytest.mark.parametrize(
    "containers", [(jhub_cont, ldap_cont)], indirect=["containers"]
)
def test_ldap_person_hook(build_image, network, containers):
    """
    Test that the ldap_person_hook is able to create an LDAP DIT entry,
    with the provided JupyterHub Spawner attribute.
    """
    test_logger.info("Start of ldap person hook testing")
    client = docker.from_env()
    username = "ldap-user"
    auth_headers = {"Remote-User": username}
    assert wait_for_site(JHUB_URL, valid_status_code=401) is True
    with requests.Session() as session:
        # Login
        login_response = session.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = session.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        dn_str = "/telephoneNumber=23012303403/SN=My Surname/CN=" + username
        # Pass LDAP DN for creation on spawn
        post_dn = session.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = session.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "{}-{}".format("jupyter", username)
        wait_min = 5
        if not wait_for_container(client, container_name, minutes=wait_min):
            raise RuntimeError(
                "No container with name: {} appeared within: {} minutes".format(
                    service_name, wait_min
                )
            )

        spawned_container = get_container(client, container_name)
        assert spawned_container is not None

        # Search openldap for person
        search_base = "dc=example,dc=org"
        search_filter = (
            "(&(objectclass=Person)(telephoneNumber=23012303403)"
            "(SN=My Surname)(CN=" + username + "))"
        )

        conn_manager = ConnectionManager(
            "127.0.0.1", user=LDAP_USER, password=LDAP_PASSWORD
        )
        conn_manager.connect()
        assert conn_manager.is_connected()
        success = search_for(
            conn_manager.get_connection(),
            search_base,
            search_filter,
            attributes=ALL_ATTRIBUTES,
        )
        assert success

        attributes = conn_manager.get_response_attributes()
        assert attributes["objectClass"] == ["person"]
        assert attributes["telephoneNumber"] == ["23012303403"]
        assert attributes["sn"] == ["My Surname"]
        assert attributes["cn"] == [username]
        assert attributes["description"] == ["A default person account"]

        # Shutdown the container
        # Delete the spawned service
        delete_headers = {"Referer": urljoin(JHUB_URL, "/hub/"), "Origin": JHUB_URL}

        jhub_user = get_container_user(spawned_container)
        assert jhub_user is not None
        assert username == jhub_user
        delete_url = urljoin(JHUB_URL, "/hub/api/users/{}/server".format(jhub_user))

        deleted = delete(session, delete_url, headers=delete_headers)
        assert deleted

        # Remove the stopped container
        spawned_container.stop()
        spawned_container.wait()
        spawned_container.remove()

        deleted_container = get_container(client, container_name)
        assert deleted_container is None


jhub_dynamic_config_path = join(config_path, "jhub", "ldap_person_dynamic_attr_hook.py")
jhub_dynamic_target_config = "/etc/jupyterhub/jupyterhub_config.py"
jhub_dynamic_cont = {
    "image": JHUB_IMAGE,
    "name": JHUB_IMAGE_NAME,
    "mounts": [
        Mount(
            source=jhub_dynamic_config_path,
            target=jhub_dynamic_target_config,
            read_only=True,
            type="bind",
        ),
        docker_mount,
    ],
    "ports": {PORT: PORT},
    "network": LDAP_NETWORK_NAME,
    "detach": "True",
    "command": "jupyterhub --debug -f " + jhub_target_config,
}


@pytest.mark.parametrize("build_image", [jhub_image_spec], indirect=["build_image"])
@pytest.mark.parametrize("network", [ldap_network_config], indirect=["network"])
@pytest.mark.parametrize(
    "containers", [(jhub_dynamic_cont, ldap_cont)], indirect=["containers"]
)
def test_ldap_person_dynamic_attr_hook(build_image, network, containers):
    """
    Test that the ldap_person_hook is able to create an LDAP DIT entry,
    with a dynamic provided spawner attribute
    """
    test_logger.info("Start of ldap person dynamic attribute hook")
    client = docker.from_env()
    username = "a-new-dynamic-user"
    auth_headers = {"Remote-User": username}
    assert wait_for_site(JHUB_URL, valid_status_code=401) is True
    with requests.Session() as session:
        # Login
        login_response = session.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = session.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        desc = "The first description"
        dn_str = (
            "/description="
            + desc
            + "/telephoneNumber=23012303403/SN=My Surname/CN="
            + username
        )
        # Pass LDAP DN for creation on spawn
        post_dn = session.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = session.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "{}-{}".format("jupyter", username)
        wait_min = 5
        if not wait_for_container(client, container_name, minutes=wait_min):
            raise RuntimeError(
                "No container with name: {} appeared within: {} minutes".format(
                    service_name, wait_min
                )
            )

        spawned_container = get_container(client, container_name)
        assert spawned_container is not None

        # Search openldap for person
        search_base = "dc=example,dc=org"
        search_filter = (
            "(&(objectclass=Person)(description="
            + desc
            + ")(telephoneNumber=23012303403)(SN=My Surname)(CN="
            + username
            + "))"
        )

        conn_manager = ConnectionManager(
            "127.0.0.1", user=LDAP_USER, password=LDAP_PASSWORD
        )
        conn_manager.connect()
        assert conn_manager.is_connected()
        success = search_for(
            conn_manager.get_connection(),
            search_base,
            search_filter,
            attributes=ALL_ATTRIBUTES,
        )
        assert success

        attributes = conn_manager.get_response_attributes()
        assert attributes["objectClass"] == ["person"]
        assert attributes["telephoneNumber"] == ["23012303403"]
        assert attributes["sn"] == ["My Surname"]
        assert attributes["cn"] == [username]
        assert attributes["description"] == [desc]

        # Check that the notebook has the description env
        spawned_container = get_container(client, container_name)
        container_desc = get_container_env(spawned_container, env_key="description")
        assert desc == container_desc

        container_static_desc = get_container_env(
            spawned_container, env_key="static_description"
        )
        assert "Static description" == container_static_desc

        # Shutdown the container
        delete_headers = {"Referer": urljoin(JHUB_URL, "/hub/"), "Origin": JHUB_URL}

        jhub_user = get_container_user(spawned_container)
        assert jhub_user is not None
        assert username == jhub_user
        delete_url = urljoin(JHUB_URL, "/hub/api/users/{}/server".format(jhub_user))

        deleted = delete(session, delete_url, headers=delete_headers)
        assert deleted

        # Remove the stopped container
        spawned_container.stop()
        spawned_container.wait()
        spawned_container.remove()

        deleted_container = get_container(client, container_name)
        assert deleted_container is None


jhub_obj_spw_config_path = join(config_path, "jhub", "ldap_object_spawner_hook.py")
jhub_obj_spw_target_config = "/etc/jupyterhub/jupyterhub_config.py"
jhub_obj_spw_cont = {
    "image": JHUB_IMAGE,
    "name": JHUB_IMAGE_NAME,
    "mounts": [
        Mount(
            source=jhub_obj_spw_config_path,
            target=jhub_obj_spw_target_config,
            read_only=True,
            type="bind",
        ),
        docker_mount,
    ],
    "ports": {PORT: PORT},
    "network": LDAP_NETWORK_NAME,
    "detach": "True",
    "command": "jupyterhub --debug -f " + jhub_obj_spw_target_config,
}


@pytest.mark.parametrize("build_image", [jhub_image_spec], indirect=["build_image"])
@pytest.mark.parametrize("network", [ldap_network_config], indirect=["network"])
@pytest.mark.parametrize(
    "containers", [(jhub_obj_spw_cont, ldap_cont)], indirect=["containers"]
)
def test_dynamic_object_spawner_attributes(build_image, network, containers):
    """
    Test that the ldap_person_hook is able to create an LDAP DIT entry,
    with a dynamic provided spawner attribute
    """
    test_logger.info("Start of ldap dynamic object spawner attributes testing")
    client = docker.from_env()
    username = "mynewuser"
    auth_headers = {"Remote-User": username}
    assert wait_for_site(JHUB_URL, valid_status_code=401) is True
    with requests.Session() as session:
        # Login
        login_response = session.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = session.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        desc = "The first description"
        dn_str = (
            "/description="
            + desc
            + "/telephoneNumber=23012303403/SN=My Surname/CN="
            + username
        )
        # Pass LDAP DN for creation on spawn
        post_dn = session.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = session.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "{}-{}".format("jupyter", username)
        wait_min = 5
        if not wait_for_container(client, container_name, minutes=wait_min):
            raise RuntimeError(
                "No container with name: {} appeared within: {} minutes".format(
                    service_name, wait_min
                )
            )

        spawned_container = get_container(client, container_name)
        assert spawned_container is not None

        # Shutdown the container
        delete_headers = {"Referer": urljoin(JHUB_URL, "/hub/"), "Origin": JHUB_URL}

        jhub_user = get_container_user(spawned_container)
        assert jhub_user is not None
        assert username == jhub_user
        delete_url = urljoin(JHUB_URL, "/hub/api/users/{}/server".format(jhub_user))

        deleted = delete(session, delete_url, headers=delete_headers)
        assert deleted

        # Remove the stopped container
        spawned_container.stop()
        spawned_container.wait()
        spawned_container.remove()

        deleted_container = get_container(client, container_name)
        assert deleted_container is None

        ####

        # Respawn, ensure that it is loaded correctly from DIT
        spawn_response = session.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        # Validate that the env is still correct
        spawned_container = get_container(client, container_name)
        jhub_user = get_container_user(spawned_container)
        assert jhub_user is not None
        assert username == jhub_user

        # Validate that the ldap DIT still only has 1 entry
        search_base = "dc=example,dc=org"
        search_filter = (
            "(&(objectclass=inetOrgPerson)"
            "(objectclass=posixAccount)(uid="
            + username
            + ")(telephoneNumber=23012303403)(SN=My Surname)(CN="
            + username
            + "))"
        )

        conn_manager = ConnectionManager(
            "127.0.0.1", user=LDAP_USER, password=LDAP_PASSWORD
        )
        conn_manager.connect()
        assert conn_manager.is_connected()
        success = search_for(
            conn_manager.get_connection(),
            search_base,
            search_filter,
            attributes=ALL_ATTRIBUTES,
        )
        assert success

        # 1 entry
        assert len(conn_manager.get_response()) == 1
        # Extract attributes from entry
        attributes = conn_manager.get_response_attributes()
        assert attributes["objectClass"] == ["inetOrgPerson", "posixAccount"]
        assert attributes["telephoneNumber"] == ["23012303403"]
        assert attributes["sn"] == ["My Surname"]
        assert attributes["cn"] == [username]
        assert attributes["uid"] == [username]

        # Shutdown the container
        # Delete the spawned service
        delete_headers = {"Referer": urljoin(JHUB_URL, "/hub/"), "Origin": JHUB_URL}

        jhub_user = get_container_user(spawned_container)
        assert jhub_user is not None
        delete_url = urljoin(JHUB_URL, "/hub/api/users/{}/server".format(jhub_user))

        deleted = delete(session, delete_url, headers=delete_headers)
        assert deleted

        # Remove the stopped container
        spawned_container.stop()
        spawned_container.wait()
        spawned_container.remove()

        deleted_container = get_container(client, container_name)
        assert deleted_container is None

import docker
import os
import requests
import logging
import pytest
from ldap3 import ALL_ATTRIBUTES
from ldap_hooks import search_for, ConnectionManager
from os.path import join, dirname, realpath
from docker.types import Mount
from docker.errors import NotFound
from .util import wait_for_site

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
    with requests.Session() as s:
        # Login
        login_response = s.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = s.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        dn_str = "/telephoneNumber=23012303403/SN=My Surname/CN=" + username
        # Pass LDAP DN for creation on spawn
        post_dn = s.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = s.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "jupyter-" + username
        spawned = False
        wait_attempts = 20
        while not spawned and wait_attempts > 0:
            try:
                client.containers.get(container_name)
                spawned = True
            except NotFound:
                pass
            wait_attempts -= 1

        post_spawn_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        assert len(post_spawn_containers) > 0

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

        # Teardown notebook
        user_container = client.containers.get(container_name)
        resp = s.delete(
            JHUB_URL + "/hub/api/users/{}/server".format(user),
            headers={"Referer": "{}/hub/".format(JHUB_URL)},
        )
        assert resp.status_code == 204
        user_container.stop()
        user_container.wait()
        user_container.remove()

        wait_attempts = 20
        removed = False
        while not removed and wait_attempts > 0:
            try:
                client.containers.get(container_name)
            except NotFound:
                removed = True
            wait_attempts -= 1

        post_jupyter_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        # double check it is gone
        assert len(post_jupyter_containers) == 0


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
    with requests.Session() as s:
        # Login
        login_response = s.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = s.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        desc = "The first description"
        dn_str = (
            "/description="
            + desc
            + "/telephoneNumber=23012303403/SN=My Surname/CN="
            + username
        )
        # Pass LDAP DN for creation on spawn
        post_dn = s.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = s.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "jupyter-" + username
        spawned = False
        wait_attempts = 20
        while not spawned and wait_attempts > 0:
            try:
                client.containers.get(container_name)
                spawned = True
            except NotFound:
                wait_attempts -= 1

        post_spawn_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        assert len(post_spawn_containers) > 0

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
        user_container = client.containers.get(container_name)
        container_desc = user_container.attrs["Config"]["Env"][0]
        assert "description=" + desc == container_desc

        container_static_desc = user_container.attrs["Config"]["Env"][1]
        assert "static_description=Static description" == container_static_desc

        # Teardown notebook
        resp = s.delete(
            JHUB_URL + "/hub/api/users/{}/server".format(username),
            headers={"Referer": "{}/hub/".format(JHUB_URL)},
        )
        assert resp.status_code == 204
        user_container.stop()
        user_container.wait()
        user_container.remove()

        wait_attempts = 20
        removed = False
        while not removed and wait_attempts > 0:
            try:
                client.containers.get(container_name)
            except NotFound:
                removed = True
            wait_attempts -= 1

        post_jupyter_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        # double check it is gone
        assert len(post_jupyter_containers) == 0


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
    with requests.Session() as s:
        # Login
        login_response = s.post(JHUB_URL + "/hub/login", headers=auth_headers)
        assert login_response.status_code == 200

        resp = s.get(JHUB_URL + "/hub/home")
        assert resp.status_code == 200

        desc = "The first description"
        dn_str = (
            "/description="
            + desc
            + "/telephoneNumber=23012303403/SN=My Surname/CN="
            + username
        )
        # Pass LDAP DN for creation on spawn
        post_dn = s.post(
            JHUB_URL + "/hub/user-data", json={"data": {"PersonDN": dn_str}}
        )
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = s.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        container_name = "jupyter-" + username
        spawned = False
        wait_attempts = 20
        while not spawned and wait_attempts > 0:
            try:
                client.containers.get(container_name)
                spawned = True
            except NotFound:
                wait_attempts -= 1

        # Check that the notebook has the NB_USER env
        user_container = client.containers.get(container_name)
        container_nbuser = user_container.attrs["Config"]["Env"][0]
        assert "NB_USER=" + username == container_nbuser

        # Teardown notebook
        resp = s.delete(
            JHUB_URL + "/hub/api/users/{}/server".format(username),
            headers={"Referer": "{}/hub/".format(JHUB_URL)},
        )
        assert resp.status_code == 204
        user_container.stop()
        user_container.wait()
        user_container.remove()

        wait_attempts = 20
        removed = False
        while not removed and wait_attempts > 0:
            try:
                client.containers.get(container_name)
            except NotFound:
                removed = True
            wait_attempts -= 1

        post_jupyter_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        # double check it is gone
        assert len(post_jupyter_containers) == 0

        # Respawn, ensure that it is loaded correctly from DIT
        spawn_response = s.post(JHUB_URL + "/hub/spawn")
        assert spawn_response.status_code == 200

        # Validate that the env is still correct
        user_container = client.containers.get(container_name)
        container_nbuser = user_container.attrs["Config"]["Env"][0]
        assert "NB_USER=" + username == container_nbuser

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

        # Teardown notebook
        resp = s.delete(
            JHUB_URL + "/hub/api/users/{}/server".format(username),
            headers={"Referer": "{}/hub/".format(JHUB_URL)},
        )
        assert resp.status_code == 204
        user_container.stop()
        user_container.wait()
        user_container.remove()

        wait_attempts = 20
        removed = False
        while not removed and wait_attempts > 0:
            try:
                client.containers.get(container_name)
            except NotFound:
                removed = True
            wait_attempts -= 1

        post_jupyter_containers = [
            jup_container
            for jup_container in client.containers.list()
            if "jupyter-" in jup_container.name
        ]
        # double check it is gone
        assert len(post_jupyter_containers) == 0

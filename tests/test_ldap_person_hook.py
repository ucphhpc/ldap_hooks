import requests
import docker
import pytest
import time
from ldap3 import ALL_ATTRIBUTES
from ldap_hooks import search_for, ConnectionManager
from os.path import join, dirname, realpath
from docker.types import Mount

# root dir
docker_path = dirname(dirname(realpath(__file__)))

JHUB_IMAGE_NAME = "jupyterhub"
JHUB_IMAGE_TAG = "test"
JHUB_IMAGE = "".join([JHUB_IMAGE_NAME, ":", JHUB_IMAGE_TAG])

jhub_image_spec = {'path': docker_path, 'tag': JHUB_IMAGE,
                   'rm': 'True', 'pull': 'True'}

LDAP_IMAGE_PATH = 'osixia/openldap'
LDAP_IMAGE_NAME = 'openldap'
LDAP_IMAGE_TAG = '1.2.3'
LDAP_IMAGE = ''.join([LDAP_IMAGE_PATH, ':', LDAP_IMAGE_TAG])

JHUB_URL = "http://127.0.0.1:8000"
LDAP_URL = "http://openldap"

# Config setup
config_path = join(dirname(realpath(__file__)), 'configs')

jhub_config_path = join(config_path, 'jhub', 'ldap_person_hook.py')
jhub_target_config = '/etc/jupyterhub/jupyterhub_config.py'

ldap_schema = join(config_path, 'openldap', 'mount_schema')
ldap_target_schema = '/container/service/slapd/assets/config/bootstrap/schema'

ldap_servers = join(config_path, 'openldap', 'openldap-servers')
ldap_target_servers = '/opt/openldap-servers'

LDAP_NETWORK_NAME = 'jhub_ldap_network'
ldap_network_config = {'name': LDAP_NETWORK_NAME,
                       'driver': 'bridge',
                       'attachable': True}

# container cmd
jhub_cont = {'image': JHUB_IMAGE, 'name': JHUB_IMAGE_NAME,
             'mounts': [Mount(source=jhub_config_path,
                              target=jhub_target_config,
                              read_only=True,
                              type='bind'),
                        Mount(source='/var/run/docker.sock',
                              target='/var/run/docker.sock',
                              read_only=True,
                              type='bind')],
             'ports': {8000: 8000},
             'network': LDAP_NETWORK_NAME,
             'detach': 'True',
             'command': 'jupyterhub --debug -f ' + jhub_target_config}

LDAP_DOMAIN = 'example.org'
LDAP_USER = 'cn=admin,dc=example,dc=org'
LDAP_PASSWORD = 'dummyldap_password'

ldap_cont = {'image': LDAP_IMAGE, 'name': LDAP_IMAGE_NAME,
             'mounts': [Mount(source=ldap_schema,
                              target=ldap_target_schema,
                              read_only=False,
                              type='bind'),
                        Mount(source=ldap_servers,
                              target=ldap_target_servers,
                              read_only=False,
                              type='bind')],
             'ports': {389: 389, 636: 636},
             'network': LDAP_NETWORK_NAME,
             'detach': 'True',
             'environment': {'LDAP_DOMAIN': LDAP_DOMAIN,
                             'LDAP_ADMIN_PASSWORD': LDAP_PASSWORD,
                             'LDAP_CONFIG_PASSWORD': LDAP_PASSWORD,
                             'LDAP_RFC2307BIS_SCHEMA': 'true'},
             'command': '--copy-service'}


@pytest.mark.parametrize('build_image', [jhub_image_spec],
                         indirect=['build_image'])
@pytest.mark.parametrize('network', [ldap_network_config],
                         indirect=['network'])
@pytest.mark.parametrize('containers', [(jhub_cont, ldap_cont)],
                         indirect=['containers'])
def test_ldap_person_hook(build_image, network, containers):
    """
    Test that the ldap_person_hook is able to create an LDAP DIT entry,
    with the provided JupyterHub Spawner attribute.
    """
    # not ideal, wait for the jhub container to start, update with proper check
    time.sleep(5)
    client = docker.from_env()
    containers = client.containers.list()
    assert len(containers) > 0
    with requests.Session() as s:
        ready = False
        while not ready:
            resp = s.get(''.join([JHUB_URL, '/hub/home']))
            if resp.status_code != 404:
                ready = True

        # Login
        user = "a-new-user"
        login_response = s.post(JHUB_URL + '/hub/login',
                                headers={'Remote-User': user})
        assert login_response.status_code == 200

        resp = s.get(JHUB_URL + '/hub/home')
        assert resp.status_code == 200

        dn_str = '/telephoneNumber=23012303403/SN=My Surname/CN=' + user
        # Pass LDAP DN for creation on spawn
        post_dn = s.post(JHUB_URL + '/hub/user-data',
                         json={'data': {'PersonDN': dn_str}})
        assert post_dn.status_code == 200

        # Spawn notebook
        spawn_response = s.post(JHUB_URL + '/hub/spawn')

        assert spawn_response.status_code == 200
        time.sleep(10)
        post_spawn_containers = client.containers.list()
        jupyter_containers = [jup_container for jup_container in
                              post_spawn_containers
                              if "jupyter-" in jup_container.name]
        assert len(jupyter_containers) > 0

        # Search openldap for person
        search_base = 'dc=example,dc=org'
        search_filter = '(&(objectclass=Person)(telephoneNumber=23012303403)' \
            '(SN=My Surname)(CN=a-new-user))'

        conn_manager = ConnectionManager('127.0.0.1',
                                         user=LDAP_USER,
                                         password=LDAP_PASSWORD)
        conn_manager.connect()
        assert conn_manager.is_connected()
        success = search_for(conn_manager.get_connection(),
                             search_base,
                             search_filter,
                             attributes=ALL_ATTRIBUTES)
        assert success

        attributes = conn_manager.get_response_attributes()
        assert attributes['objectClass'] == ['person']
        assert attributes['telephoneNumber'] == ['23012303403']
        assert attributes['sn'] == ['My Surname']
        assert attributes['cn'] == ['a-new-user']
        assert attributes['description'] == ['A default person account']

import requests
import docker
import pytest
import time
from os.path import join, dirname, realpath
from docker.types import Mount


JHUB_IMAGE_PATH = 'nielsbohr/jupyterhub'
JHUB_IMAGE_NAME = "jupyterhub"
JHUB_IMAGE_TAG = "latest"
JHUB_IMAGE = "".join([JHUB_IMAGE_PATH, ":", JHUB_IMAGE_TAG])

LDAP_IMAGE_PATH = 'osixia/openldap'
LDAP_IMAGE_NAME = 'openldap'
LDAP_IMAGE_TAG = '1.2.3'
LDAP_IMAGE = ''.join([LDAP_IMAGE_PATH, ':', LDAP_IMAGE_TAG])

JHUB_URL = "http://127.0.0.1:8000"
LDAP_URL = ""
# root dir
docker_path = dirname(dirname(realpath(__file__)))

# Config setup
config_path = join(dirname(realpath(__file__)), 'configs')

jhub_config_path = join(config_path, 'jhub', 'ldap_person_hook.py')
jhub_target_config = '/etc/jupyterhub/jupyterhub_config.py'

ldap_schema = join(config_path, 'openldap', 'mount_schema')
ldap_target_schema = '/container/service/slapd/assets/config/bootstrap/schema'

ldap_servers = join(config_path, 'openldap', 'openldap-servers')
ldap_target_servers = '/opt/openldap-servers'

# container cmd
jhub_cont = {'image': JHUB_IMAGE, 'name': JHUB_IMAGE_NAME,
             'mounts': [Mount(source=jhub_config_path,
                              target=jhub_target_config,
                              read_only=True,
                              type='bind')],
             'ports': {8000: 8000},
             'detach': 'True'}

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
             'detach': 'True',
             'environement': {'LDAP_DOMAIN': 'example.org',
                              'LDAP_ADMIN_PASSWORD': 'dummyldap_password',
                              'LDAP_CONFIG_PASSWORD': 'dummyldap_password',
                              'LDAP_RFC2307BIS_SCHEMA': 'true'}}


@pytest.mark.parametrize('container', [jhub_cont, ldap_cont],
                         indirect=['container'])
def test_ldap_person_hook(container):
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
            try:
                s.get(JHUB_URL)
                if s.get(JHUB_URL + "/hub/login").status_code == 200:
                    ready = True
            except requests.exceptions.ConnectionError:
                pass

        # login
        user = "a-new-user"
        # next to hub/home, else the login by
        #  default will return 500 because it will
        #  try and start a server right away with the new user
        # Which fails because the default
        #  spawner requires a matching local username
        login_response = s.post(JHUB_URL + "/hub/login?next=/hub/home",
                                data={"username": user,
                                      "password": "password"})
        assert login_response.status_code == 200
        resp = s.get(JHUB_URL + '/hub/home')
        assert resp.status_code == 200

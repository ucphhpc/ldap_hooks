import requests
import docker
import pytest
import time
from os.path import join, dirname, realpath
from docker.types import Mount

IMAGE_NAME = "jupyterhub"
IMAGE_TAG = "test"
IMAGE = "".join([IMAGE_NAME, ":", IMAGE_TAG])

JHUB_URL = "http://127.0.0.1:8000"
# root dir
docker_path = dirname(dirname(realpath(__file__)))

# mount paths
config_path = join(dirname(realpath(__file__)), 'jupyterhub_configs',
                   'dummy_auth_config.py')

# image build
jhub_image = {'path': docker_path, 'tag': IMAGE,
              'rm': 'True', 'pull': 'True'}

target_config = '/etc/jupyterhub/jupyterhub_config.py'
# container cmd
jhub_cont = {'image': IMAGE, 'name': IMAGE_NAME,
             'mounts': [Mount(source=config_path,
                              target=target_config,
                              read_only=True,
                              type='bind')],
             'ports': {8000: 8000},
             'detach': 'True'}


@pytest.mark.parametrize('build_image', [jhub_image], indirect=['build_image'])
@pytest.mark.parametrize('container', [jhub_cont], indirect=['container'])
def test_dummy_auth(build_image, container):
    """
    Test that the client is able to.
    - Once authenticated, pass a correctly formatted Mount Header
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

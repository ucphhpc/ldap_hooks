import time
import pytest
import docker
from docker.errors import NotFound


@pytest.fixture(scope="function")
def network(request):
    """Create the docker network that the hub and server services will
    use to communicate.
    """
    client = docker.from_env()
    _network = client.networks.create(**request.param)
    yield _network
    _network.remove()
    removed = False
    while not removed:
        try:
            client.networks.get(_network.id)
        except NotFound:
            removed = True


@pytest.fixture(scope="function")
def build_image(request):
    client = docker.from_env()
    _image = client.images.build(**request.param)
    yield _image

    # Remove image after test usage
    image_obj = _image[0]
    image_id = image_obj.id
    client.images.remove(image_obj.tags[0], force=True)

    removed = False
    while not removed:
        try:
            client.images.get(image_id)
        except NotFound:
            removed = True


@pytest.fixture(scope="function")
def pull_image(request):
    client = docker.from_env()
    _image = client.images.pull(**request.param)
    yield _image

    # Remove image after test usage
    image_obj = _image[0]
    image_id = image_obj.id
    client.images.remove(image_obj.tags[0], force=True)

    removed = False
    while not removed:
        try:
            client.images.get(image_id)
        except NotFound:
            removed = True


@pytest.fixture(scope="function")
def container(request):
    client = docker.from_env()
    _container = client.containers.run(**request.param)
    while _container.status != "running":
        time.sleep(1)
        _container = client.containers.get(_container.name)

    yield _container
    assert hasattr(_container, "id")

    _container.stop()
    _container.wait()
    _container.remove()
    removed = False
    while not removed:
        try:
            client.containers.get(_container.id)
        except NotFound:
            removed = True


@pytest.fixture(scope="function")
def containers(request):
    if not isinstance(request.param, (list, tuple)):
        raise TypeError(
            "request: must be a list or tuple, "
            "was of type: {}".format(type(request.param))
        )

    client = docker.from_env()
    containers = []
    for c in request.param:
        _container = client.containers.run(**c)
        attempts = 0
        while _container.status != "running":
            time.sleep(1)
            _container = client.containers.get(_container.name)
            attempts = attempts + 1
            if attempts == 30:
                raise RuntimeError(
                    "Container: {} never started correctly, "
                    "err: {}".format(_container.name, _container.status)
                )

        containers.append(_container)

    yield containers

    for container in containers:
        container.stop()
        container.wait()
        container.remove()
        removed = False
        while not removed:
            try:
                client.containers.get(container.id)
            except NotFound:
                removed = True

import time
import requests


def get_site(session, url, headers=None, valid_status_code=200):
    if not headers:
        headers = {}
    try:
        resp = session.get(url, headers=headers)
        if resp.status_code == valid_status_code:
            return True
    except requests.exceptions.ConnectionError:
        pass
    return False


# Waits for 5 minutes for a site to be ready
def _wait_for_site(session, url, timeout=60, valid_status_code=200, require_xsrf=False):
    attempts = 0
    while attempts < timeout:
        if get_site(session, url, valid_status_code=valid_status_code):
            if require_xsrf:
                if "_xsrf" in session.cookies:
                    return True
            else:
                return True
        attempts += 1
        time.sleep(1)
    return False


def wait_for_site(
    url,
    timeout=60,
    valid_status_code=200,
    auth_url=None,
    auth_headers=None,
    require_xsrf=False,
):
    with requests.Session() as s:
        if auth_url:
            auth_resp = s.get(auth_url, headers=auth_headers)
            if auth_resp.status_code != 200:
                return False

        if _wait_for_site(
            s,
            url,
            timeout=timeout,
            valid_status_code=valid_status_code,
            require_xsrf=require_xsrf,
        ):
            if require_xsrf:
                if "_xsrf" in s.cookies:
                    return True
            else:
                return True
    return False


def delete(session, url, timeout=60, headers=None, valid_status_code=204):
    if not headers:
        headers = {}

    attempts = 0
    while attempts < timeout:
        resp = session.delete(url, headers=headers)
        if resp.status_code == valid_status_code:
            return True
        attempts += 1
        time.sleep(1)
    return False


def wait_for_container(client, container_name, minutes=5):
    found = False
    sec_waited = 0
    sleep_for = 20
    while not found:
        container = get_container(client, container_name)
        if container:
            found = True

        time.sleep(sleep_for)
        sec_waited += sleep_for
        if sec_waited > (minutes * 60):
            break

    return found


def get_container(client, container_name):
    containers = client.containers.list()
    for container in containers:
        if container.name == container_name:
            return container
    return None


def get_container_env(container, env_key=None):
    # If no Env, the service might not be started succesfully
    if "Env" not in container.attrs["Config"]:
        return None

    envs = {}
    for env in container.attrs["Config"]["Env"]:
        key, value = env.split("=", 1)
        envs[key] = value

    if env_key and env_key in envs:
        return envs[env_key]
    return None


def get_container_user(container):
    return get_container_env(container, env_key="JUPYTERHUB_USER")

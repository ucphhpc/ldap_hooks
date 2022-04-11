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

FROM jupyterhub/jupyterhub:2.2.2

ADD ldap_hooks /app/ldap_hooks
ADD setup.py /app/setup.py
ADD version.py /app/version.py
ADD requirements.txt /app/requirements.txt
ADD requirements-dev.txt /app/requirements-dev.txt
ADD tests/requirements.txt /app/tests/requirements.txt

WORKDIR /app
RUN pip install -r requirements.txt \
    && touch README.rst \
    && python setup.py install

RUN pip install dockerspawner \
        jhub-authenticators

# Make sure the jupyter_config is mounted upon run
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
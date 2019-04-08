# Example config
from ldap_hooks import hello_hook
c = get_config()

c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.hub_ip = '0.0.0.0'
c.JupyterHub.port = 80

# Spawner setup
c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
c.DockerSpawner.image = 'nielsbohr/base-notebook:latest'
c.DockerSpawner.network_name = 'docker-migrid_default'
c.DockerSpawner.pre_spawn_hook = hello_hook

# Authenticator setup
c.JupyterHub.authenticator_class = 'jhubauthenticators.DummyAuthenticator'
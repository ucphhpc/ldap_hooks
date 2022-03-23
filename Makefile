OWNER=ucphhpc
IMAGE=ldap_hooks
TAG=edge
ARGS=

.PHONY: build

all: init clean build push

# Link to the original defaults.env if none other is setup
init:
ifeq (,$(wildcard ./.env))
	ln -s defaults.env .env
endif

build:
	python3 setup.py sdist
	python3 setup.py bdist_wheel
	docker build -t ${OWNER}/${IMAGE}:${TAG} $(ARGS) .

clean:
	rm -fr dist build *.egg-info
	docker rmi -f ${OWNER}/${IMAGE}:${TAG}

push:
	docker push ${OWNER}/${IMAGE}:${TAG}

installtests:
	pip3 install -r tests/requirements.txt

# The tests requires access to the docker socket
test:
	pytest -s -v tests/

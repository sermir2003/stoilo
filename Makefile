.PHONY: gen-proto clean-proto clone-boinc install-python-lib-dev

COMMIT := $(shell git rev-parse --short=10 HEAD)
DIFF := $(shell git diff --quiet HEAD || git diff HEAD | sha256sum | cut -c1-8)
VERSION := v-$(COMMIT)-$(or $(DIFF),0)

clean-proto:
	./proto/protobuf_compiler.sh --clean

gen-proto:
	./proto/protobuf_compiler.sh --gen

clone-boinc:
	git clone https://github.com/boinc/boinc.git
	cd boinc && git checkout 301a029af1dda1d6bc94e55826a3eab8773a4930

install-python-lib-dev:
	pip install -e python_lib[dev]

build-server:
	docker build \
		--file server/deploy/Dockerfile \
		--no-cache-filter project \
		--tag cr.yandex/$(REGISTRY_ID)/server:$(VERSION) \
		.

build-volunteer:
	docker build \
		--file volunteer/Dockerfile \
		--tag cr.yandex/$(REGISTRY_ID)/volunteer:$(VERSION) \
		volunteer/

push-server:
	docker push cr.yandex/$(REGISTRY_ID)/server:$(VERSION)

push-volunteer:
	docker push cr.yandex/$(REGISTRY_ID)/volunteer:$(VERSION)

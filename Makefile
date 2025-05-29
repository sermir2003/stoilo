.PHONY: gen-proto clean-proto clone-boinc install-python-lib-dev

clean-proto:
	./proto/protobuf_compiler.sh --clean

gen-proto:
	./proto/protobuf_compiler.sh --gen

clone-boinc:
	git clone https://github.com/boinc/boinc.git

install-python-lib-dev:
	pip install -e python_lib[dev]

build-server:
	docker build \
		--file server/deploy/Dockerfile \
		--tag cr.yandex/crpdphpe78a3t7g3ikvt/server:$(VERSION) \
		.

build-volunteer:
	docker build \
		--file volunteer/Dockerfile \
		--tag cr.yandex/crpdphpe78a3t7g3ikvt/volunteer:$(VERSION) \
		volunteer/

push-server:
	docker push cr.yandex/crpdphpe78a3t7g3ikvt/server:$(VERSION)

push-volunteer:
	docker push cr.yandex/crpdphpe78a3t7g3ikvt/volunteer:$(VERSION)

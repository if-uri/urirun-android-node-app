PYTHON ?= python3
SERVICE_APK_DIR ?= /home/tom/github/if-uri/urirun-service-android-node/apk

.PHONY: check apk publish-apk docker-apk build-and-publish clean toolchain

check:
	$(PYTHON) -m py_compile main.py
	$(PYTHON) -m pytest -q tests

toolchain:
	@command -v buildozer >/dev/null || { echo "buildozer not found. Install: python3 -m pip install --user buildozer"; exit 1; }
	@command -v java >/dev/null || { echo "java not found. Install a JDK required by Buildozer."; exit 1; }

apk: toolchain
	buildozer android debug

publish-apk:
	mkdir -p "$(SERVICE_APK_DIR)"
	test -d bin || { echo "bin/ not found. Run: make apk"; exit 1; }
	ls bin/*.apk >/dev/null 2>&1 || { echo "No APK in bin/. Run: make apk"; exit 1; }
	cp bin/*.apk "$(SERVICE_APK_DIR)/"
	ls -l "$(SERVICE_APK_DIR)"/*.apk

build-and-publish:
	./scripts/build-and-publish.sh

docker-apk:
	./scripts/docker-build-apk.sh

clean:
	rm -rf .buildozer bin __pycache__ .pytest_cache tests/__pycache__

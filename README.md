# urirun-android-node-app

Android application that exposes a small URI node directly on the device.

It is different from the webpage relay:

- webpage relay: phone opens `http://HOST:8195/`, host controls it through a relay;
- Android node app: APK runs on Android and exposes its own local API, usually
  `http://ANDROID_IP:8765`.

## URI API

The app listens on port `8765` and exposes:

```text
GET  /health
GET  /routes
POST /run
```

Example run payload:

```json
{
  "uri": "android://device/app/query/status",
  "payload": {}
}
```

Initial routes:

```text
android://device/app/query/status
android://device/app/query/routes
android://device/app/query/log
android://device/app/command/ping
android://device/termux/query/status
android://device/termux/command/start
android://device/termux/command/stop
```

The Termux routes are best-effort. They require a bootstrap script at:

```text
/data/data/com.termux/files/home/.urirun-node/run-node.sh
```

## Build

Install the Android build toolchain first:

```bash
python3 -m pip install --user buildozer
# install Java/JDK + Android SDK/NDK dependencies required by Buildozer
```

Then build:

```bash
cd /home/tom/github/if-uri/urirun-android-node-app
make apk
```

Publish the APK to the service that serves `http://HOST:8195/apk/`:

```bash
make publish-apk
```

The service checks this repo's `bin/` directory directly, so a successful
Buildozer build is also enough for the APK to appear in `/apk/`.

One-command build and publish:

```bash
./scripts/build-and-publish.sh
```

## Build in Docker

If you do not want to install Buildozer and the Android toolchain directly on
the host, build the debug APK in Docker:

```bash
cd /home/tom/github/if-uri/urirun-android-node-app
make docker-apk
```

This builds the local image from `docker/Dockerfile.android-dev`, runs
`buildozer android debug` with the repo mounted at `/work`, then copies
`bin/*.apk` to:

```text
/home/tom/github/if-uri/urirun-service-android-node/apk
```

If Docker is installed but the command says the daemon is not reachable, run it
from a normal host terminal with Docker access.

## Test the URI API

After installing and opening the APK on Android, read the URL shown in the app,
then test from the host:

```bash
./scripts/test-uri-api.sh http://ANDROID_IP:8765
```

Equivalent raw calls:

```bash
curl -fsS http://ANDROID_IP:8765/health
curl -fsS http://ANDROID_IP:8765/routes
curl -fsS -X POST http://ANDROID_IP:8765/run \
  -H 'Content-Type: application/json' \
  -d '{"uri":"android://device/app/command/ping","payload":{"from":"host"}}'
```

## Local checks

```bash
make check
```

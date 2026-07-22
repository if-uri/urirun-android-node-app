# urirun-android-node-app

The canonical Termux bootstrap served by `urirun-service-android-node` lives at
`scripts/bootstrap-termux.sh`. The former `android-node-app` prototype is retired.

Android application that exposes a URI node HTTP API directly on the device.

Contrast with the webpage relay approach:

| | webpage relay | Android node app |
|---|---|---|
| who runs code | host PC | Android device |
| phone requirement | any browser | APK installed |
| API address | `http://HOST:8195/` | `http://ANDROID_IP:8765` |
| background operation | tab must stay open | foreground service, survives minimize |

## Architecture

The APK runs two components:

- **Kivy activity** — shows the device IP, service status, and Termux controls.
- **Foreground service** (`service/main.py`) — hosts the HTTP API in its own Android process. Declared with `foreground:sticky` so Android does not kill it when the activity is backgrounded or the screen turns off.

The activity communicates with the service via `http://127.0.0.1:8765`.

## URI API

The service listens on port `8765` (override with env `URIRUN_ANDROID_APP_PORT`).

```
GET  /health   — status JSON
GET  /routes   — list of registered URI routes
POST /run      — execute a URI
```

POST body:

```json
{ "uri": "android://device/app/command/ping", "payload": {} }
```

Available routes:

```
android://device/app/query/status       device + service info
android://device/app/query/routes       list routes
android://device/app/query/log          recent event log (last 80 entries)
android://device/app/command/ping       echo payload back

android://device/termux/query/status    Termux subprocess status
android://device/termux/command/start   launch Termux urirun node
android://device/termux/command/stop    kill Termux urirun node
```

Termux routes require a bootstrap script at:

```
/data/data/com.termux/files/home/.urirun-node/run-node.sh
```

## Requirements

| Component | Version |
|---|---|
| Android | 12+ (API 31) |
| Architecture | arm64-v8a |

## Install

Download the APK from the host node server and install it:

```
http://HOST:8195/apk/urirunnode-0.3.0-arm64-v8a-debug.apk
```

Or scan the QR code shown at `http://HOST:8195/`.

Enable **Install from unknown sources** in Android settings before installing a debug APK.

## Test the URI API

After installing and opening the APK, note the IP shown in the app, then from the host:

```bash
./scripts/test-uri-api.sh http://ANDROID_IP:8765
```

Or with raw curl:

```bash
curl -fsS http://ANDROID_IP:8765/health
curl -fsS http://ANDROID_IP:8765/routes
curl -fsS -X POST http://ANDROID_IP:8765/run \
  -H 'Content-Type: application/json' \
  -d '{"uri":"android://device/app/command/ping","payload":{"from":"host"}}'
```

## Build

### Docker (recommended)

No local Android toolchain needed. Requires Docker with access to the Docker daemon.

```bash
make docker-apk
```

This builds the image from `docker/Dockerfile.android-dev`, runs `buildozer android debug`
inside the container, and copies the APK to:

```
/home/tom/github/if-uri/urirun-service-android-node/apk/
```

Skip rebuilding the Docker image on repeated runs:

```bash
URIRUN_ANDROID_BUILD_SKIP_IMAGE=1 make docker-apk
```

#### Build cache

The Docker build uses two persistent host directories:

| Variable | Default | Contents |
|---|---|---|
| `URIRUN_BUILDOZER_CACHE` | `~/.buildozer-cache` | Android SDK, NDK, p4a recipe builds |
| `URIRUN_ANDROID_BUILD_HOME` | `~/.urirun-android-build-home` | pip user packages, Gradle cache |

A cold build (empty cache) takes 60–90 minutes. A warm build (only dist + Gradle)
takes 3–5 minutes.

#### Rebuilding after code changes

Only `main.py` and `service/main.py` change between builds. The dist is rebuilt
automatically when the dist directory is absent. Delete only the dist to avoid
invalidating the compiled recipe cache:

```bash
rm -rf .buildozer/android/platform/build-arm64-v8a/dists/urirunnode
URIRUN_ANDROID_BUILD_SKIP_IMAGE=1 make docker-apk
```

Do **not** delete `bootstrap_builds/` — it contains git-cloned submodules
(SDL2_image external deps) that cannot be re-fetched inside the network-isolated
container.

### Native (host buildozer)

```bash
make apk
```

Requires `buildozer`, a JDK, and Android SDK/NDK on the host.

### Publish to APK server

```bash
make publish-apk
```

Copies `bin/*.apk` to the `urirun-service-android-node` APK directory so the
file appears at `http://HOST:8195/apk/`.

### Key build settings (`buildozer.spec`)

| Setting | Value | Notes |
|---|---|---|
| `p4a.branch` | `release-2024.01.21` | Last stable release for Python 3.11 + NDK r25b |
| `android.ndk` | `25b` | NDK r25b, Clang 14.0.6 |
| `android.ndk_api` | `31` | Native API level compiled against |
| `android.minapi` | `31` | Minimum Android version (API 31 = Android 12) |
| `android.api` | `35` | Target API (Android 15) |
| `android.services` | `nodeservice:service/main.py:foreground:sticky` | HTTP server service |
| `android.no-byte-compile-python` | `True` | Ships `.py` source; avoids packager crash |

`android.minapi` must equal `android.ndk_api` — p4a 2024.01.21 rejects a mismatch
unless `--allow-minsdk-ndkapi-mismatch` is passed.

#### hostpython3 recipe patch

The `hostpython3` recipe (builds host-side Python used during compilation) requires
a manual patch in `.buildozer/` to prevent NDK cross-compile flags from leaking
into the host Python build and breaking `_posixsubprocess` and other shared modules:

```python
# .buildozer/android/platform/python-for-android/pythonforandroid/recipes/hostpython3/__init__.py
def get_recipe_env(self, arch=None):
    env = os.environ.copy()
    env["CC"] = "gcc"
    env["CXX"] = "g++"
    for key in ("CFLAGS", "CXXFLAGS", "LDFLAGS", "CPPFLAGS", "ARCH", "LDSHARED"):
        env.pop(key, None)
    return env
```

This patch lives only inside `.buildozer/` (not in git) and must be re-applied
after `buildozer android clean` or a fresh checkout.

## Local checks

```bash
make check
```

Runs `py_compile` on `main.py` and the pytest suite in `tests/`.

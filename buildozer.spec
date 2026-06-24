[app]
title = urirun node
package.name = urirunnode
package.domain = com.ifuri
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.3.0

requirements = python3==3.11.5,kivy==2.3.0

# p4a 2024.01.21: last release with stable Python 3.11 + NDK r25b cross-compile support.
# The 2026 master changed hostpython3 defaults to 3.14 and broke the off_t configure cache.
p4a.branch = release-2024.01.21

# Foreground service — keeps the HTTP server alive when the Kivy activity is backgrounded.
# Android kills background-process threads; a foreground service runs in its own process
# with a persistent notification and is protected from aggressive process death.
# "foreground" = calls startForeground(); "sticky" = restarted if killed by system OOM.
android.services = nodeservice:service/main.py:foreground:sticky

# Android 11 (API 30) .. Android 15 (API 35)
android.api = 35
android.minapi = 31
android.sdk = 35
android.ndk = 25b
android.ndk_api = 31
android.archs = arm64-v8a

# Permissions — FOREGROUND_SERVICE_DATA_SYNC removed: no service element was declared,
# which triggered Android 14 validation warnings.  FOREGROUND_SERVICE is sufficient
# for a generic foreground service without a typed category.
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,WAKE_LOCK,CAMERA,POST_NOTIFICATIONS,FOREGROUND_SERVICE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO

orientation = portrait
fullscreen = 0

# Ship .py instead of .pyc: p4a's byte-compile path uses a host python that resolves to None in
# this toolchain, crashing packaging with "expected str ... not NoneType". Skipping byte-compile
# avoids it; the app just bundles source (slightly larger, recompiled on first run).
android.no-byte-compile-python = True

[buildozer]
log_level = 2
warn_on_root = 1

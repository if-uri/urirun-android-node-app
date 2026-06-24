[app]
title = urirun node
package.name = urirunnode
package.domain = com.ifuri
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,sh,txt,md
version = 0.3.0

requirements = python3==3.11.5,kivy==2.3.0

# p4a 2024.01.21: last release with stable Python 3.11 + NDK r25b cross-compile support.
# The 2026 master changed hostpython3 defaults to 3.14 and broke the off_t configure cache.
p4a.branch = release-2024.01.21

# Android 12 (API 31) .. Android 15 (API 35)
# minapi = 31  -> installs on Android 12+
# api/sdk = 35 -> targets Android 15 (apps targeting 35 also run on 12/13/14)
android.api = 35
android.minapi = 31
android.sdk = 35
android.ndk = 25b
android.ndk_api = 31
# Every Android 12-15 device is 64-bit, so arm64-v8a covers them all (and halves build
# time vs. also building armeabi-v7a). Add armeabi-v7a only for 32-bit-compat hardware.
android.archs = arm64-v8a

# Modern permission model (Android 13+ replaced READ/WRITE_EXTERNAL_STORAGE with granular
# media perms; notifications and foreground-service types are now runtime-gated).
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,WAKE_LOCK,CAMERA,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1

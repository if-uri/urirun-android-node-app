[app]
title = urirun node
package.name = urirunnode
package.domain = com.ifuri
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,sh,txt,md
version = 0.2.0

requirements = python3==3.11.0,kivy==2.3.0

android.api = 33
android.minapi = 23
android.sdk = 33
android.ndk = 25b
android.ndk_api = 23
android.archs = armeabi-v7a,arm64-v8a

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1


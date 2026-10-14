[app]
title = AirMouse
package.name = airmouse
package.domain = org.example.airmouse
source.include_exts = py,png,jpg,kv
source.dir = .
requirements = python3, kivy, plyer, pyjnius
orientation = portrait
fullscreen = 1
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.sdk_path = /usr/local/lib/android/sdk
android.api = 33
android.minapi = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license_agreements = True
p4a.url = https://github.com/kivy/python-for-android.git
p4a.branch = 2024.01.21
presplash.filename = assets/presplash.png
icon.filename = assets/icon.png
presplash_color = #FFFFFF
version = 1.1.0

[buildozer]
copy_to_bin = False
debug = 1

[android]
android.archs = arm64-v8a, armeabi-v7a
android.ndk = 25b
android.aab = False
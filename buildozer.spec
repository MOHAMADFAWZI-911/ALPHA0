[app]
title = AirMouse
package.name = airmouse
package.domain = org.example.airmouse
source.dir = .
source.include_exts = py,png,jpg,kv
requirements = python3, kivy, plyer, pyjnius
orientation = portrait
fullscreen = 1
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
p4a.branch = master
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
android.accept_sdk_license_agreements = True
android.aab = False

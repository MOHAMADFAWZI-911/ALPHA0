# AirMouse - Phone as Air Mouse

Turn your Android phone into a wireless air mouse using gyroscope.

## How it works
- **Phone (Android)**: Kivy app reads gyroscope (Game Rotation Vector fusion when available, else gyro+accel) and sends `MOVE`/`CLICK` over UDP WiFi.
- **PC**: `pc_server.py` listens on UDP 5555 and moves cursor via `pynput`.

## Quick start
1. **PC**: `pip install pynput` then `python pc_server.py` - note the IP printed.
2. **Phone**: Install APK, enter PC IP, tap Connect, move phone to control cursor.

## Build APK
Push to `main` triggers GitHub Action, or locally (Linux/WSL):
```
buildozer -v android debug
```

## Sensors
Best: `TYPE_GAME_ROTATION_VECTOR` (gyro+accel fusion, no magnet drift) via pyjnius. Fallback: `plyer` gyroscope with bias calibration and deadzone.

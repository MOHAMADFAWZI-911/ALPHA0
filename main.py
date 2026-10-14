import socket
import time
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.utils import platform

# Plyer sensors - primary fallback
try:
    from plyer import gyroscope, accelerometer
except ImportError:
    gyroscope = None
    accelerometer = None

# Pyjnius for Game Rotation Vector (best sensor fusion on Android)
_jnius_available = False
_Sensor = None
_SensorManager = None
_sensor_manager = None
_game_rotation_sensor = None
_jnius_listener = None

if platform == 'android':
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        _Sensor = autoclass('android.hardware.Sensor')
        _SensorManager = autoclass('android.hardware.SensorManager')
        _jnius_available = True
    except Exception as e:
        print(f"Pyjnius not available: {e}")
        _jnius_available = False


class AirMouseClientApp(App):
    def build(self):
        self.sensitivity = 1.0
        self.connected = False
        self.dragging = False
        self.pc_port = 5555
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        # Sensor fusion state
        self.last_time = time.time()
        self.yaw = 0.0
        self.pitch = 0.0
        self.bias_x = 0.0
        self.bias_y = 0.0
        self.calib_samples = []
        self.is_calibrating = False
        # Scale: pixels per radian - tuned for comfortable movement
        self.base_scale = 900
        # Complementary filter alpha (gyro trust)
        self.alpha = 0.98
        # Jnius sensor state
        self._jnius_yaw = 0.0
        self._jnius_pitch = 0.0
        self._jnius_has_data = False
        self.use_jnius = _jnius_available

        # --- UI ---
        root = BoxLayout(orientation='vertical', padding=12, spacing=8)

        # Title
        root.add_widget(Label(text="AirMouse", font_size=26, size_hint_y=0.12, bold=True))

        # IP row
        ip_row = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=6)
        ip_row.add_widget(Label(text="PC IP:", size_hint_x=0.22))
        self.ip_input = TextInput(text="192.168.1.100", multiline=False, hint_text="192.168.1.100", size_hint_x=0.48)
        ip_row.add_widget(self.ip_input)
        self.connect_btn = Button(text="Connect", size_hint_x=0.30, background_color=(0.2, 0.6, 0.9, 1))
        self.connect_btn.bind(on_press=self.toggle_connection)
        ip_row.add_widget(self.connect_btn)
        root.add_widget(ip_row)

        # Status
        self.status_label = Label(text="Not connected - enter PC IP and tap Connect", font_size=14, size_hint_y=0.10, color=(0.9, 0.9, 0.9, 1))
        root.add_widget(self.status_label)

        # Sensitivity
        sens_row = BoxLayout(orientation='horizontal', size_hint_y=0.10, spacing=6)
        sens_row.add_widget(Label(text="Sensitivity:", size_hint_x=0.35))
        self.sensitivity_slider = Slider(min=0.3, max=3.0, value=1.0, size_hint_x=0.45)
        self.sensitivity_slider.bind(value=self.on_sensitivity_change)
        sens_row.add_widget(self.sensitivity_slider)
        self.sens_label = Label(text="1.0x", size_hint_x=0.20)
        sens_row.add_widget(self.sens_label)
        root.add_widget(sens_row)

        # Click buttons grid
        grid = GridLayout(cols=2, spacing=6, size_hint_y=0.36)
        grid.add_widget(Button(text="Left Click", on_press=lambda _: self.send_click("left")))
        grid.add_widget(Button(text="Right Click", on_press=lambda _: self.send_click("right")))
        self.drag_btn = Button(text="Drag (hold)")
        self.drag_btn.bind(on_press=self.toggle_drag)
        grid.add_widget(self.drag_btn)
        grid.add_widget(Button(text="Middle Click", on_press=lambda _: self.send_click("middle")))
        grid.add_widget(Button(text="Scroll Up", on_press=lambda _: self.send_click("scroll_up")))
        grid.add_widget(Button(text="Scroll Down", on_press=lambda _: self.send_click("scroll_down")))
        root.add_widget(grid)

        # Bottom row
        bottom = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=6)
        bottom.add_widget(Button(text="Calibrate", on_press=self.calibrate))
        bottom.add_widget(Button(text="Center", on_press=self.recenter))
        root.add_widget(bottom)

        # Init sensors
        self.init_sensors()
        # Schedule movement at 60Hz for low latency
        Clock.schedule_interval(self.send_position, 1.0 / 60.0)

        return root

    # --- Sensor init ---
    def init_sensors(self):
        if self.use_jnius:
            try:
                self._init_jnius_sensor()
                self.status_label.text = "Sensor: Game Rotation Vector (fused)"
                return
            except Exception as e:
                print(f"Jnius sensor failed, fallback to plyer: {e}")
                self.use_jnius = False
        # Fallback: plyer
        try:
            if gyroscope and gyroscope.is_available():
                gyroscope.enable()
            if accelerometer and accelerometer.is_available():
                accelerometer.enable()
            if gyroscope or accelerometer:
                self.status_label.text = "Sensor: Gyro+Accel (complementary filter)"
            else:
                self.status_label.text = "No sensors found - buttons only"
        except Exception as e:
            self.status_label.text = f"Sensor error: {e}"

    def _init_jnius_sensor(self):
        from jnius import PythonJavaClass, java_method
        activity = PythonActivity.mActivity
        self._sensor_manager = activity.getSystemService(Context.SENSOR_SERVICE)
        self._game_rotation_sensor = self._sensor_manager.getDefaultSensor(15)  # TYPE_GAME_ROTATION_VECTOR
        # TYPE_GAME_ROTATION_VECTOR = 15, TYPE_ROTATION_VECTOR = 11
        # Try GAME_ROTATION_VECTOR first, fallback to ROTATION_VECTOR
        if self._game_rotation_sensor is None:
            self._game_rotation_sensor = self._sensor_manager.getDefaultSensor(11)
        if self._game_rotation_sensor is None:
            raise Exception("No rotation vector sensor")

        outer = self

        class RotationListener(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/SensorEventListener']
            @java_method('(Landroid/hardware/Sensor;I)V')
            def onAccuracyChanged(self, sensor, accuracy):
                pass
            @java_method('(Landroid/hardware/SensorEvent;)V')
            def onSensorChanged(self, event):
                try:
                    vals = event.values
                    # vals[0..3] is quaternion, convert to yaw/pitch
                    # Use Android SensorManager.getOrientation
                    from jnius import autoclass
                    SensorManagerCls = autoclass('android.hardware.SensorManager')
                    R = [0]*9
                    orient = [0]*3
                    SensorManagerCls.getRotationMatrixFromVector(R, vals)
                    SensorManagerCls.getOrientation(R, orient)
                    # orient[0]=azimuth(yaw), [1]=pitch, [2]=roll
                    outer._jnius_yaw = orient[0]
                    outer._jnius_pitch = orient[1]
                    outer._jnius_has_data = True
                except Exception as e:
                    print(f"Sensor event error: {e}")

        self._jnius_listener = RotationListener()
        self._sensor_manager.registerListener(
            self._jnius_listener,
            self._game_rotation_sensor,
            1  # SENSOR_DELAY_GAME = 1
        )

    def on_pause(self):
        try:
            if self.use_jnius and self._sensor_manager and self._jnius_listener:
                self._sensor_manager.unregisterListener(self._jnius_listener)
            else:
                if gyroscope:
                    gyroscope.disable()
                if accelerometer:
                    accelerometer.disable()
        except:
            pass
        return True

    def on_resume(self):
        self.init_sensors()
        self.last_time = time.time()

    # --- UI callbacks ---
    def on_sensitivity_change(self, instance, value):
        self.sensitivity = value
        self.sens_label.text = f"{value:.1f}x"

    def toggle_connection(self, instance):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        ip = self.ip_input.text.strip()
        if not ip:
            self.status_label.text = "Enter PC IP first"
            return
        # Validate IP
        parts = ip.split(".")
        if len(parts) != 4:
            self.status_label.text = "Invalid IP (e.g. 192.168.1.10)"
            return
        self.pc_ip = ip
        try:
            self.sock.sendto(b"HELLO", (self.pc_ip, self.pc_port))
            self.connected = True
            self.connect_btn.text = "Disconnect"
            self.connect_btn.background_color = (0.9, 0.3, 0.3, 1)
            self.status_label.text = f"Connected to {self.pc_ip}:{self.pc_port} - move phone to control"
            self.last_time = time.time()
            self.yaw = 0
            self.pitch = 0
        except Exception as e:
            self.status_label.text = f"Connect failed: {e}"

    def disconnect(self):
        self.connected = False
        self.connect_btn.text = "Connect"
        self.connect_btn.background_color = (0.2, 0.6, 0.9, 1)
        self.status_label.text = "Disconnected"
        if self.dragging:
            self.dragging = False
            self.drag_btn.text = "Drag (hold)"
            self.drag_btn.background_color = (1, 1, 1, 1)

    def calibrate(self, instance):
        self.status_label.text = "Calibrating... hold still"
        self.is_calibrating = True
        self.calib_samples = []
        Clock.schedule_once(self._finish_calibrate, 1.0)

    def _finish_calibrate(self, dt):
        if self.calib_samples:
            avg_x = sum(s[0] for s in self.calib_samples) / len(self.calib_samples)
            avg_y = sum(s[1] for s in self.calib_samples) / len(self.calib_samples)
            self.bias_x = avg_x
            self.bias_y = avg_y
        self.is_calibrating = False
        self.status_label.text = f"Calibrated bias: {self.bias_x:.3f}, {self.bias_y:.3f}"

    def recenter(self, instance):
        self.yaw = 0
        self.pitch = 0
        self._jnius_yaw = 0
        self._jnius_pitch = 0
        self.status_label.text = "Recentered"

    # --- Input handling ---
    def send_position(self, dt):
        if not self.connected:
            return
        now = time.time()
        real_dt = now - self.last_time
        self.last_time = now
        if real_dt <= 0 or real_dt > 0.1:
            real_dt = 1.0 / 60.0

        dx = 0.0
        dy = 0.0

        # Path 1: Jnius Game Rotation Vector (best)
        if self.use_jnius and self._jnius_has_data:
            # Delta from last orientation - use yaw/pitch change
            # We track previous yaw/pitch and compute delta
            if not hasattr(self, '_prev_j_yaw'):
                self._prev_j_yaw = self._jnius_yaw
                self._prev_j_pitch = self._jnius_pitch
                return
            dyaw = self._jnius_yaw - self._prev_j_yaw
            dpitch = self._jnius_pitch - self._prev_j_pitch
            # Handle wrap-around for yaw (-pi to pi)
            if dyaw > 3.14:
                dyaw -= 6.28
            elif dyaw < -3.14:
                dyaw += 6.28
            self._prev_j_yaw = self._jnius_yaw
            self._prev_j_pitch = self._jnius_pitch
            # Deadzone to ignore tiny drift
            if abs(dyaw) < 0.001:
                dyaw = 0
            if abs(dpitch) < 0.001:
                dpitch = 0
            dx = dyaw * self.base_scale * self.sensitivity
            dy = -dpitch * self.base_scale * self.sensitivity
        else:
            # Path 2: Plyer gyro + accel complementary filter
            try:
                gx = gy = 0.0
                if gyroscope and gyroscope.is_available():
                    # plyer returns (x,y,z) angular velocity rad/s
                    vals = gyroscope.rotation
                    if vals and len(vals) >= 2:
                        gx, gy = float(vals[0]), float(vals[1])
                        if self.is_calibrating:
                            self.calib_samples.append((gx, gy))
                            return
                        gx -= self.bias_x
                        gy -= self.bias_y
                        # Deadzone
                        if abs(gx) < 0.05:
                            gx = 0
                        if abs(gy) < 0.05:
                            gy = 0
                        # Integrate: delta = angular velocity * dt
                        # Map: yaw (y-axis) -> horizontal, pitch (x-axis) -> vertical
                        dx = gy * real_dt * self.base_scale * self.sensitivity
                        dy = -gx * real_dt * self.base_scale * self.sensitivity
                # Optional: accel correction for drift (complementary)
                # We keep it simple - gyro integration is enough for relative mouse
            except Exception as e:
                # Don't spam status every frame
                print(f"Gyro read error: {e}")
                return

        if dx == 0 and dy == 0:
            return
        # Clamp to avoid huge jumps
        dx = max(-800, min(800, dx))
        dy = max(-800, min(800, dy))
        self.send_to_pc(f"MOVE:{dx:.2f},{dy:.2f}")

    def send_click(self, click_type):
        if not self.connected:
            self.status_label.text = "Not connected - tap Connect first"
            return
        self.send_to_pc(f"CLICK:{click_type}")

    def toggle_drag(self, instance):
        if not self.connected:
            self.status_label.text = "Not connected"
            return
        if not self.dragging:
            self.send_to_pc("CLICK:drag_start")
            self.dragging = True
            self.drag_btn.text = "Release Drag"
            self.drag_btn.background_color = (0.9, 0.6, 0.2, 1)
            self.status_label.text = "Dragging..."
        else:
            self.send_to_pc("CLICK:drag_end")
            self.dragging = False
            self.drag_btn.text = "Drag (hold)"
            self.drag_btn.background_color = (1, 1, 1, 1)
            self.status_label.text = "Released"

    def send_to_pc(self, data):
        if not hasattr(self, 'pc_ip'):
            return
        try:
            self.sock.sendto(data.encode('utf-8'), (self.pc_ip, self.pc_port))
        except Exception as e:
            self.status_label.text = f"Send Error: {e}"
            print(f"Send error: {e}")


if __name__ == "__main__":
    AirMouseClientApp().run()

"""
AirMouse PC Server - receives UDP from phone and controls mouse.
Run on PC:  pip install pynput
            python pc_server.py
Phone must be on same WiFi and enter this PC IP in app.
"""
import socket
import sys

try:
    from pynput.mouse import Button, Controller
except ImportError:
    print("Missing pynput. Install: pip install pynput")
    sys.exit(1)

PORT = 5555
mouse = Controller()
dragging = False

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
print(f"AirMouse PC Server listening on 0.0.0.0:{PORT}")
print(f"Your IP: {socket.gethostbyname(socket.gethostname())}")
print("Enter this IP in the phone app and tap Connect.")
print("Move phone to control cursor. Ctrl+C to quit.\n")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        msg = data.decode("utf-8", errors="ignore").strip()
        if msg == "HELLO":
            print(f"[+] Connected: {addr}")
            continue
        if msg.startswith("MOVE:"):
            try:
                _, coords = msg.split(":", 1)
                dx_str, dy_str = coords.split(",")
                dx = float(dx_str)
                dy = float(dy_str)
                # Clamp
                dx = max(-800, min(800, dx))
                dy = max(-800, min(800, dy))
                mouse.move(dx, dy)
            except Exception as e:
                print(f"MOVE parse error: {msg} -> {e}")
        elif msg.startswith("CLICK:"):
            action = msg.split(":", 1)[1].strip()
            if action == "left":
                mouse.click(Button.left, 1)
                print(f"[{addr}] Left click")
            elif action == "right":
                mouse.click(Button.right, 1)
                print(f"[{addr}] Right click")
            elif action == "middle":
                mouse.click(Button.middle, 1)
                print(f"[{addr}] Middle click")
            elif action == "scroll_up":
                mouse.scroll(0, 2)
            elif action == "scroll_down":
                mouse.scroll(0, -2)
            elif action == "drag_start":
                mouse.press(Button.left)
                dragging = True
                print(f"[{addr}] Drag start")
            elif action == "drag_end":
                mouse.release(Button.left)
                dragging = False
                print(f"[{addr}] Drag end")
            else:
                print(f"Unknown click: {action}")
        else:
            print(f"Unknown msg from {addr}: {msg}")
    except KeyboardInterrupt:
        if dragging:
            try:
                mouse.release(Button.left)
            except:
                pass
        print("\nExiting.")
        break
    except Exception as e:
        print(f"Error: {e}")

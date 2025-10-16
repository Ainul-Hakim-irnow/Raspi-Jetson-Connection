# multi_jetson_sender.py

import cv2
import tkinter as tk
from tkinter import ttk, messagebox
from pypylon import pylon
import numpy as np
import threading
from PIL import Image, ImageTk
import socket
import time
import struct

# --- CONFIGURATION ---
# !!! IMPORTANT: Set a unique ID (1-6) for each Jetson !!!
JETSON_ID = 1 

# !!! IMPORTANT: Set the Raspberry Pi's permanent wired IP address !!!
RPI_IP_ADDRESS = "10.10.10.8"
# ---------------------


class RealTimeAnalysisApp:
    def __init__(self, root, rpi_ip, jetson_id):
        self.root = root
        self.root.title(f"Jetson Sender (ID: {jetson_id})")
        self.rpi_ip = rpi_ip
        self.rpi_port = 65432
        self.jetson_id = jetson_id

        # Window variables
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}")
        self.processing_width = 1280
        self.processing_height = 720

        # Camera variables
        self.camera_running = False
        self.camera = None
        self.converter = None

        # Control variables
        self.exposure_value = tk.IntVar(value=5000)
        self.brightness_value = tk.DoubleVar(value=0.0)
        self.contrast_value = tk.DoubleVar(value=0.0)

        # Networking
        self.latest_frame = None
        self.send_thread = None
        self.stop_sending = threading.Event()

        self.setup_gui()

    def send_image_periodically(self):
        """Periodically sends the latest captured frame with a prepended ID."""
        while not self.stop_sending.is_set():
            if self.latest_frame is not None:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((self.rpi_ip, self.rpi_port))
                        
                        # Compress the frame to JPEG
                        _, buffer = cv2.imencode('.jpg', self.latest_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        data = buffer.tobytes()
                        
                        # NEW PROTOCOL: [ID][LENGTH][IMAGE DATA]
                        # Pack the ID (1 byte) and the length (4 bytes, big-endian)
                        header = struct.pack('>BL', self.jetson_id, len(data))
                        
                        # Send the header followed by the image data
                        s.sendall(header + data)
                        print(f"Sent {len(data)} bytes to Raspberry Pi from ID {self.jetson_id}.")
                except Exception as e:
                    print(f"Failed to send image: {e}")
            
            # Wait for 30 seconds before sending the next image
            time.sleep(30)

    # --- NO OTHER CHANGES ARE NEEDED FOR THE REST OF THE SCRIPT ---
    # (The rest of your GUI and camera control code remains the same)

    def setup_gui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(main_frame, width=250)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        tk.Label(control_frame, text="Exposure").pack(pady=5, anchor="w")
        exposure_frame = tk.Frame(control_frame)
        exposure_frame.pack(fill=tk.X, pady=5)
        ttk.Scale(exposure_frame, from_=2, to=1000000, variable=self.exposure_value, orient=tk.HORIZONTAL, command=self.update_exposure_display).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.exposure_entry = tk.Entry(exposure_frame, width=8)
        self.exposure_entry.pack(side=tk.RIGHT, padx=5)
        self.exposure_entry.insert(0, f"{self.exposure_value.get()}")
        self.exposure_entry.bind("<Return>", self.set_exposure_value)

        tk.Label(control_frame, text="Brightness").pack(pady=5, anchor="w")
        brightness_frame = tk.Frame(control_frame)
        brightness_frame.pack(fill=tk.X, pady=5)
        ttk.Scale(brightness_frame, from_=-1.0, to=1.0, variable=self.brightness_value, orient=tk.HORIZONTAL, command=self.update_brightness_display).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.brightness_entry = tk.Entry(brightness_frame, width=8)
        self.brightness_entry.pack(side=tk.RIGHT, padx=5)
        self.brightness_entry.insert(0, f"{self.brightness_value.get():.3f}")
        self.brightness_entry.bind("<Return>", self.set_brightness_value)

        tk.Label(control_frame, text="Contrast").pack(pady=5, anchor="w")
        contrast_frame = tk.Frame(control_frame)
        contrast_frame.pack(fill=tk.X, pady=5)
        ttk.Scale(contrast_frame, from_=-1.0, to=1.0, variable=self.contrast_value, orient=tk.HORIZONTAL, command=self.update_contrast_display).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.contrast_entry = tk.Entry(contrast_frame, width=8)
        self.contrast_entry.pack(side=tk.RIGHT, padx=5)
        self.contrast_entry.insert(0, f"{self.contrast_value.get():.3f}")
        self.contrast_entry.bind("<Return>", self.set_contrast_value)

        tk.Button(control_frame, text="Start Camera", command=self.start_camera).pack(fill=tk.X, pady=5)
        tk.Button(control_frame, text="Stop Camera", command=self.stop_camera).pack(fill=tk.X, pady=5)

        self.video_frame = tk.Label(main_frame, text="Camera Feed")
        self.video_frame.pack(fill=tk.BOTH, expand=True)

    def update_exposure_display(self, _):
        self.exposure_entry.delete(0, tk.END)
        self.exposure_entry.insert(0, str(self.exposure_value.get()))

    def set_exposure_value(self, event):
        try:
            value = int(self.exposure_entry.get())
            if 2 <= value <= 1000000:
                self.exposure_value.set(value)
            else:
                messagebox.showerror("Invalid Input", "Exposure must be an integer between 2 and 1,000,000.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid integer for exposure.")

    def update_brightness_display(self, _):
        self.brightness_entry.delete(0, tk.END)
        self.brightness_entry.insert(0, f"{self.brightness_value.get():.3f}")

    def set_brightness_value(self, event):
        try:
            value = float(self.brightness_entry.get())
            if -1.0 <= value <= 1.0:
                self.brightness_value.set(value)
            else:
                messagebox.showerror("Invalid Input", "Brightness must be a float between -1.0 and 1.0.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid float for brightness.")

    def update_contrast_display(self, _):
        self.contrast_entry.delete(0, tk.END)
        self.contrast_entry.insert(0, f"{self.contrast_value.get():.3f}")

    def set_contrast_value(self, event):
        try:
            value = float(self.contrast_entry.get())
            if -1.0 <= value <= 1.0:
                self.contrast_value.set(value)
            else:
                messagebox.showerror("Invalid Input", "Contrast must be a float between -1.0 and 1.0.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid float for contrast.")

    def start_camera(self):
        if not self.camera_running:
            self.camera_running = True
            threading.Thread(target=self.start_basler_camera, daemon=True).start()
            self.stop_sending.clear()
            self.send_thread = threading.Thread(target=self.send_image_periodically, daemon=True)
            self.send_thread.start()

    def start_basler_camera(self):
        try:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            self.camera.Open()
            self.camera.ExposureTime.SetValue(self.exposure_value.get())
            self.camera.BslBrightness.SetValue(self.brightness_value.get())
            self.camera.BslContrast.SetValue(self.contrast_value.get())
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            self.update_video_feed()
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to start camera: {e}")
            self.camera_running = False

    def update_video_feed(self):
        if self.camera_running and self.camera.IsGrabbing():
            try:
                grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                if grab_result.GrabSucceeded():
                    self.camera.ExposureTime.SetValue(self.exposure_value.get())
                    self.camera.BslBrightness.SetValue(self.brightness_value.get())
                    self.camera.BslContrast.SetValue(self.contrast_value.get())
                    image = self.converter.Convert(grab_result)
                    frame = image.GetArray()
                    self.latest_frame = cv2.resize(frame, (self.processing_width, self.processing_height))
                    display_frame_rgb = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(display_frame_rgb)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_frame.imgtk = imgtk
                    self.video_frame.configure(image=imgtk)
                grab_result.Release()
            except Exception as e:
                print(f"Error in video feed: {e}")
            self.root.after(30, self.update_video_feed)

    def stop_camera(self):
        self.camera_running = False
        self.stop_sending.set()
        if self.send_thread:
            self.send_thread.join()
        if self.camera and self.camera.IsGrabbing():
            self.camera.StopGrabbing()
        if self.camera:
            self.camera.Close()
        self.camera = None
        self.video_frame.config(image='', text="Camera Feed")

    def on_close(self):
        self.stop_camera()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RealTimeAnalysisApp(root, RPI_IP_ADDRESS, JETSON_ID)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

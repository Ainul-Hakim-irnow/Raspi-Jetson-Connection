# multi_rpi_receiver.py

import sys
import socket
import struct
import io
import os
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QGridLayout, QWidget, QStatusBar
from PySide6.QtCore import Qt, QThread, Signal, QObject, Slot
from PySide6.QtGui import QPixmap, QFont

# --- CONFIGURATION ---
GRID_ROWS = 2
GRID_COLS = 3
# ---------------------

class NetworkWorker(QObject):
    """Handles network communication and emits signals with received data."""
    # NEW SIGNAL: Emits Jetson ID (int) and image data (bytes)
    image_received = Signal(int, bytes)
    status_update = Signal(str)

    def __init__(self, host='0.0.0.0', port=65432):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None

    def start_server(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10) # Listen for up to 10 connections
        self.status_update.emit(f"Listening on port {self.port}...")

        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                # Spawn a new thread to handle this specific client
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
            except OSError:
                if self.running: self.status_update.emit("Server socket was closed.")
                break
            except Exception as e:
                self.status_update.emit(f"Error accepting connections: {e}")

    def handle_client(self, conn, addr):
        """Receives image data from a single connected client."""
        self.status_update.emit(f"Connection from {addr[0]}:{addr[1]}")
        with conn:
            try:
                # NEW PROTOCOL: [ID (1 byte)][LENGTH (4 bytes)][IMAGE DATA]
                header_data = self.recvall(conn, 5) # Read the first 5 bytes (ID + Length)
                if not header_data:
                    return

                jetson_id, data_len = struct.unpack('>BL', header_data)
                
                img_data = self.recvall(conn, data_len)
                if not img_data:
                    return

                self.status_update.emit(f"Received {len(img_data) / 1024:.2f} KB from Jetson ID {jetson_id}.")
                self.image_received.emit(jetson_id, img_data)

            except Exception as e:
                self.status_update.emit(f"Error handling client {addr}: {e}")

    def recvall(self, sock, n):
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        return data

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.status_update.emit("Server stopped.")


class MultiImageReceiverApp(QMainWindow):
    """Main application window with a grid display for multiple camera feeds."""
    def __init__(self, rows, cols):
        super().__init__()
        self.setWindowTitle("Multi-Camera Receiver (Raspberry Pi CM5)")
        self.setGeometry(100, 100, 1920, 1080)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.grid_layout = QGridLayout(central_widget)

        self.image_labels = {} # Dictionary to hold labels, mapped by Jetson ID
        font = QFont()
        font.setPointSize(24)

        for i in range(rows * cols):
            jetson_id = i + 1
            label = QLabel(f"Waiting for Jetson ID: {jetson_id}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(font)
            label.setStyleSheet("background-color: black; color: white; border: 1px solid #555;")
            
            self.image_labels[jetson_id] = label
            row, col = divmod(i, cols)
            self.grid_layout.addWidget(label, row, col)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.image_dir = "received_images"
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

        self.setup_network_thread()

    def setup_network_thread(self):
        self.thread = QThread()
        self.worker = NetworkWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start_server)
        self.worker.image_received.connect(self.update_image)
        self.worker.status_update.connect(self.show_status_message)
        self.thread.start()

    @Slot(int, bytes)
    def update_image(self, jetson_id, img_data):
        """Slot to handle new image data and update the correct label in the grid."""
        if jetson_id not in self.image_labels:
            self.show_status_message(f"Received image from unknown Jetson ID: {jetson_id}")
            return

        try:
            pixmap = QPixmap()
            pixmap.loadFromData(img_data, "JPG")
            
            self.save_image(pixmap, jetson_id)

            label_to_update = self.image_labels[jetson_id]
            scaled_pixmap = pixmap.scaled(
                label_to_update.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label_to_update.setPixmap(scaled_pixmap)

        except Exception as e:
            self.show_status_message(f"Error displaying image from ID {jetson_id}: {e}")

    @Slot(str)
    def show_status_message(self, message):
        print(message)
        self.status_bar.showMessage(message, 5000)

    def save_image(self, pixmap, jetson_id):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.image_dir, f"jetson_image_ID_{jetson_id}_{timestamp}.jpg")
        if not pixmap.save(filename, "JPG"):
            self.show_status_message(f"Failed to save image {filename}")

    def closeEvent(self, event):
        self.show_status_message("Closing application...")
        self.worker.stop()
        self.thread.quit()
        self.thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MultiImageReceiverApp(rows=GRID_ROWS, cols=GRID_COLS)
    window.show()
    sys.exit(app.exec())

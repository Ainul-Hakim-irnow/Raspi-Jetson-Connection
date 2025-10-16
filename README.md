# Jetson to Raspberry Pi Multi-Camera Streaming System

## 1. Project Overview

This system provides a robust solution for capturing images from multiple NVIDIA Jetson devices and streaming them over a dedicated wired network to a central receiver. The receiver, which can be a Raspberry Pi or a Linux laptop, displays all incoming camera feeds in a real-time grid view and saves each image with a timestamp.

This setup is designed for reliability and scalability, making it ideal for monitoring applications in environments like a factory floor where a stable, private network is preferred over a potentially congested Wi-Fi network.

**Core Technologies:**
* **Sender (Jetson):** Python, Basler Pylon SDK, OpenCV, Tkinter for camera controls.
* **Receiver (Pi/Laptop):** Python, PySide6 for the multi-view GUI.
* **Network:** TCP/IP over a dedicated Ethernet network.



---

## 2. Features

* **Multi-Camera Support:** Scalable architecture designed to handle up to 6 Jetson cameras simultaneously.
* **Centralized Display:** The receiver shows all camera feeds in a single, organized grid.
* **Dedicated Network:** Uses a private, wired network for high reliability and to avoid interference from other networks.
* **Real-time Monitoring:** Images are captured and sent periodically (default is every 30 seconds).
* **Automatic Archiving:** The receiver automatically saves every received image, named with the Jetson's ID and a timestamp.
* **Remote Camera Control:** The sender application on each Jetson provides a GUI to adjust camera parameters like exposure, brightness, and contrast.

---

## 3. System Requirements

### Hardware
* **Sender(s):** 1 to 6 NVIDIA Jetson devices (e.g., Orin Nano).
* **Camera(s):** Basler or other Pylon-compatible cameras.
* **Receiver:** A Raspberry Pi (CM5 recommended) or a laptop running a Linux distribution (e.g., Ubuntu).
* **Network Switch:** A basic, unmanaged Ethernet switch with enough ports for all devices.
* **Cables:** Ethernet (RJ45) cables for each device.

### Software Prerequisites

#### On EACH Jetson (Sender)
1.  **Python 3** (usually pre-installed).
2.  **Basler Pylon SDK:** Must be downloaded from the Basler website and installed on each Jetson.
3.  **Python Libraries:**
    ```bash
    pip install pypylon opencv-python-headless numpy pillow
    ```

#### On the Raspberry Pi / Laptop (Receiver)
1.  **Python 3**.
2.  **PySide6 Library:**
    ```bash
    # Recommended method
    pip install PySide6

    # Alternative for Debian/Ubuntu based systems
    # sudo apt-get update
    # sudo apt-get install python3-pyside6
    ```

---

## 4. Setup and Configuration

This is the most critical part. Follow these steps to ensure the network is configured correctly.

### Step 1: Physical Network Setup
1.  Connect **all** Jetsons and the Raspberry Pi/Laptop receiver to the network switch using Ethernet cables.
2.  **Do not** connect the switch to the internet or any other network. This creates our private, isolated communication channel.
3.  You can keep your devices connected to Wi-Fi for internet access (for setup, updates, etc.), as our configuration will ensure the video traffic uses the private wired network.

### Step 2: Configure Permanent Static IP Addresses
To ensure devices can always find each other, we will assign them fixed addresses on our private network (`10.10.10.x`).

#### On the Receiver (Raspberry Pi Example)
We will assign the receiver the permanent IP **`10.10.10.8`**.
1.  Open a terminal and edit the `dhcpcd` configuration file:
    ```bash
    sudo nano /etc/dhcpcd.conf
    ```
2.  Scroll to the bottom of the file and add the following lines:
    ```
    # Static IP configuration for the private camera network
    interface eth0
    static ip_address=10.10.10.8/24
    ```
3.  Save the file (`Ctrl+O`, `Enter`) and exit (`Ctrl+X`).
4.  Reboot the Raspberry Pi to apply the settings:
    ```bash
    sudo reboot
    ```

#### On EACH Jetson
Each Jetson needs a **unique** static IP. We will use `10.10.10.1` for the first, `10.10.10.2` for the second, and so on.
1.  Open the graphical Network Manager on the Jetson desktop.
2.  Go to **Wired Settings** and click the cog (⚙️) icon for your wired connection (e.g., `eth0` or `enP8p1s0`).
3.  Go to the **`IPv4`** tab.
4.  Set the Method to **Manual**.
5.  Enter the details. For **Jetson 1**:
    * **Address:** `10.10.10.1`
    * **Netmask:** `255.255.255.0`
    * **Gateway:** Leave this **blank**.
6.  Click **Apply** and save. The setting should be permanent.
7.  Repeat this process for all other Jetsons, giving each a unique address (`10.10.10.2`, `10.10.10.3`, etc.).

### Step 3: Configure the Sender Scripts
On each Jetson, you must edit the `multi_jetson_sender.py` file to match your setup.

1.  **Set the Jetson's Unique ID:** This number (1-6) determines which box its video appears in on the receiver. **This must be unique for each Jetson.**
    ```python
    # For Jetson 1
    JETSON_ID = 1
    ```
    ```python
    # For Jetson 2
    JETSON_ID = 2
    ```
2.  **Set the Receiver's IP Address:** Make sure this matches the static IP you gave to the Raspberry Pi.
    ```python
    RPI_IP_ADDRESS = "10.10.10.8"
    ```

---

## 5. How to Run the System

1.  **Start the Receiver First:** On your Raspberry Pi or Laptop, navigate to the project directory and run the receiver script:
    ```bash
    python multi_rpi_receiver.py
    ```
    A window with a grid of empty boxes should appear, with the status bar showing "Listening on port 65432...".

2.  **Start the Senders:** On each Jetson, navigate to the project directory and run the sender script:
    ```bash
    python multi_jetson_sender.py
    ```
    A GUI will appear. Click the **"Start Camera"** button. After a few moments, you should see the live feed in the Jetson's local window.

3.  **Monitor:** Every 30 seconds, the Jetson will send an image to the receiver. The corresponding box in the receiver's grid view will update with the new image, and a confirmation message will print in both terminals.

---

## 6. Troubleshooting

* **Connection Errors (`Connection timed out`, `Destination Host Unreachable`):**
    * This is almost always a network configuration issue.
    * Use the `ping` command from a Jetson to the receiver: `ping 10.10.10.8`.
    * If the ping fails, carefully re-check that the static IPs are set correctly on both devices, that the IP in the sender script is correct, and that all Ethernet cables are securely plugged into the switch.

* **A Specific Jetson's Port Not Working (`NO-CARRIER` error):**
    * If `ip a` on a Jetson shows `NO-CARRIER` for its wired port and the link lights are off, it indicates a physical connection problem.
    * This has been diagnosed as a hardware failure of the Jetson's onboard Ethernet port. The most reliable solution is to use a **USB-to-Ethernet adapter** and assign the static IP to that new network interface.

* **`NameError: name 'threading' is not defined` on Receiver:**
    * You are missing `import threading` at the top of the `multi_rpi_receiver.py` script. Please ensure the line is present.

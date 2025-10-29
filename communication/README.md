# Automated Visual Inspection (AVI) Control System

## 1. Overview

This project is a distributed, real-time control system for an automated visual inspection (AVI) assembly line. It uses a central Raspberry Pi controller to manage, monitor, and collect data from multiple NVIDIA Jetson clients performing AI-based defect detection.

Communication between all devices is handled via a central MQTT broker. The system is designed for robustness, featuring automatic startup of client-side services and full remote control (start/stop) of each Jetson's inference process from the central GUI.

---

## 2. System Architecture

The system consists of three main software components:

1.  **Central Controller (`brain5.py`)**
    * **Host:** Raspberry Pi
    * **Responsibilities:**
        * Provides a Tkinter GUI for system-wide monitoring and control.
        * Tracks individual bottles as they pass sensors, calculating inspection deadlines.
        * Collects inference results from all Jetsons for each bottle.
        * Makes a final "pass" or "eject" decision.
        * Logs all completed bottles to a local SQLite database (`avi_system.db`).
        * Monitors the online/offline/stale status of all clients.
        * Publishes start/stop commands to individual Jetsons.

2.  **Jetson Launcher (`launcher.py`)**
    * **Host:** *Each* NVIDIA Jetson
    * **Responsibilities:**
        * Runs automatically on boot as a `systemd` service.
        * Connects to MQTT and listens *only* for commands (e.g., `avi/jetson/1/command`).
        * Manages the `jetson5.py` script as a separate process.
        * Starts or stops the `jetson5.py` (inference) process based on commands from the central controller.

3.  **Jetson Inference Client (`jetson5.py`)**
    * **Host:** *Each* NVIDIA Jetson
    * **Responsibilities:**
        * *Does not* run on boot. It is started on-demand by `launcher.py`.
        * Connects to the Pylon camera and runs the AI inference model.
        * Publishes inspection results (JSON) to its `avi/jetson/X/result` topic.
        * Publishes processed images (Base64) to its `avi/jetson/X/image/processed` topic.
        * Publishes a heartbeat and status for the GUI to monitor.

---

## 3. Key Files
```
/project-root/ 
├── brain5.py # Main Raspberry Pi Controller & GUI 
├── jetson5.py # Main Jetson Inference Script 
├── launcher.py # Jetson Process Manager (runs as service) 
├── avi_system.db # SQLite database (created by brain5.py) 
├── model/ 
│ └── hpi/ 
│ ├── best_model.pth # AI model weights 
│ └── metadata.json # Model class/color metadata 
└── README.md # This file
```
---

## 4. Setup and Installation

This guide assumes you have a functional network where the Raspberry Pi and all Jetsons can communicate.

### Part 1: Raspberry Pi Setup (Central Controller)

1.  **Install MQTT Broker:**
    ```bash
    sudo apt update
    sudo apt install mosquitto mosquitto-clients -y
    sudo systemctl enable mosquitto
    sudo systemctl start mosquitto
    ```

2.  **Install Python Dependencies:**
    ```bash
    pip3 install paho-mqtt pillow
    # tkinter is usually included with Python
    ```

3.  **Configure Controller Script (`brain5.py`):**
    * Ensure all constants at the top of `brain5.py` are correct, especially:
    * `MQTT_PORT` (e.g., `1999`)
    * `CONVEYOR_SPEED_MPS`
    * `SENSOR_DISTANCES`
    * `CLIENT_IDS` (must match the `JETSON_ID`s)

### Part 2: *Each* NVIDIA Jetson Setup (Inference Client)

**Repeat these 5 steps for every Jetson device.**

1.  **Enable Automatic Login (Required):**
    The `launcher.py` service needs to run *after* the graphical user has logged in. You must enable auto-login to avoid the system getting stuck at the password prompt on boot.

    * **GUI Method:**
        1.  Go to **System Settings > User Accounts**.
        2.  Click **Unlock** and enter your password.
        3.  Toggle **Automatic Login** to **ON**.

    * **Command-Line Method:**
        1.  Edit the GDM3 config file: `sudo nano /etc/gdm3/custom.conf`
        2.  Under the `[daemon]` section, uncomment and set these two lines:
            ```ini
            AutomaticLoginEnable = true
            AutomaticLogin = YOUR_USERNAME
            ```
            (Replace `YOUR_USERNAME` with your actual username, e.g., `jetson6`)
        3.  Save the file (`Ctrl+O`, `Enter`) and exit (`Ctrl+X`).

2.  **Copy Project Files:**
    * Copy `jetson5.py`, `launcher.py`, and the entire `model/` directory to a known location on the Jetson (e.g., `/home/jetson6/Documents/avi_project/`).

3.  **Install Python Dependencies:**
    ```bash
    pip3 install paho-mqtt numpy opencv-python pillow pypylon
    # You must also have torch and torchvision installed
    ```

4.  **Configure Client Scripts:**
    * **In `launcher.py`:**
        * Set `JETSON_ID` to this specific machine's ID (e.g., `"1"`, `"2"`, `"6"`).
        * Set `MQTT_BROKER_HOST` to the IP address of your Raspberry Pi (e.g., `"192.168.1.47"`).
        * Verify `MAIN_SCRIPT_PATH` points to the correct location of `jetson5.py`.
    * **In `jetson5.py`:**
        * Set `JETSON_ID` to the *same ID* as above (e.g., `"1"`, `"2"`, `"6"`).
        * Set `MQTT_BROKER_HOST` to the *same* Raspberry Pi IP.
        * Verify `WEIGHTS_PATH` and `METADATA_PATH` point to the correct model file locations.

5.  **Create `systemd` Service:**
    This will automatically run `launcher.py` every time the Jetson boots and logs in.

    1.  Create the service file:
        ```bash
        sudo nano /etc/systemd/system/jetson-launcher.service
        ```

    2.  Paste the following content into the file. **You MUST change the paths and username.**

        ```ini
        [Unit]
        Description=Jetson Launcher Service for AVI
        # This waits until after you are automatically logged in
        After=graphical.target

        [Service]
        User=jetson
        Group=jetson
        
        WorkingDirectory=/home/jetson/Documents/tcpip
        ExecStart=/usr/bin/python3 /home/jetson/Documents/tcpip/launcher.py

        # Restart the service if it ever fails
        Restart=always
        RestartSec=5s

        [Install]
        # This links it to the graphical login target
        WantedBy=graphical.target
        ```

    3.  Save the file (`Ctrl+O`, `Enter`) and exit (`Ctrl+X`).

    4.  Enable and start the service:
        ```bash
        sudo systemctl daemon-reload           # Reload systemd to find new file
        sudo systemctl enable jetson-launcher.service  # Enable it to run on boot
        sudo systemctl start jetson-launcher.service   # Start it right now
        ```
    5. Restart
       ```
       sudo systemctl restart jetson-launcher.service
       ```
    6. Stop
       ```
       sudo systemctl stop jetson-launcher.service
       ```
       

---

## 5. Running the System (Startup Sequence)

1.  Power on the **Raspberry Pi**.
2.  Ensure the `mosquitto` MQTT broker is running.
3.  Start the central controller on the Pi:
    ```bash
    python3 brain5.py
    ```
4.  Power on all **NVIDIA Jetsons**.
5.  Wait for the Jetsons to boot and automatically log in. The `jetson-launcher.service` will start `launcher.py` on each one.
6.  On the Raspi GUI, all `jetson-X` status dots will be **RED** (offline). This is normal, as only the launcher is running, not the main inference script.
7.  From the GUI, click the **"Start"** button next to each Jetson client.
8.  The `launcher.py` on each Jetson will receive the command and start the `jetson5.py` script.
9.  As each `jetson5.py` script connects to MQTT and sends its first heartbeat, its status dot on the GUI will turn **GREEN**.

The system is now fully operational.

---

## 6. Troubleshooting

**Problem: My Jetson service is failing or in a restart loop.**
(The status shows `activating (auto-restart) (Result: exit-code)`).

1.  **Check the service status:**
    ```bash
    systemctl status jetson-launcher.service
    ```
    (Look at the `Main PID` line for the `code=exited, status=...`)

2.  **View the detailed error log:**
    ```bash
    journalctl -u jetson-launcher.service
    ```
    (Scroll to the bottom for the most recent error).

3.  **Common Errors & Fixes:**
    * **Error:** `can't open file ... No such file or directory`
        * **Cause:** A typo in your `jetson-launcher.service` file.
        * **Fix:** Double-check the `ExecStart` and `WorkingDirectory` paths. Make sure they are the full, absolute paths and are spelled correctly.

    * **Error:** `ModuleNotFoundError: No module named 'paho'` (or any other module)
        * **Cause:** The Python library isn't installed for the user the service is running as.
        * **Fix:** `pip3 install paho-mqtt` (or the missing module).

    * **Error:** `(code=exited, status=2)`
        * **Cause:** This is often a Python file-not-found error (see above).
        * **Fix:** Check the `journalctl` log for the specific Python error.

    * **After fixing, always reload and restart the service:**
        ```bash
        sudo systemctl daemon-reload
        sudo systemctl restart jetson-launcher.service
        ```

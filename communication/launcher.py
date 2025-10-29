#!/usr/bin/env python3

import sys
import os
import time
import json
import logging
import paho.mqtt.client as mqtt
import subprocess

# --- CONFIGURE THIS FOR EACH JETSON ---
JETSON_ID = "1"  # E.g., "1", "2", "3"
# --- ------------------------------ ---

# --- Path to the main script to run ---
# Assumes launcher.py is in the same directory as jetson5.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "jetson5.py")

# --- MQTT Configuration ---
MQTT_BROKER_HOST = "192.168.1.47" # Use the Raspi's IP
MQTT_BROKER_PORT = 1999
MQTT_TOPIC_COMMAND = f"avi/jetson/{JETSON_ID}/command"
MQTT_TOPIC_STATUS = f"avi/status/jetson/launcher" # A new topic to report launcher status
MQTT_CLIENT_ID = f"jetson-launcher-{JETSON_ID}"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] (%(threadName)-10s) %(message)s')
log = logging.getLogger()

# --- Global process handle ---
process_handle = None

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        log.info(f"Connected to MQTT Broker at {MQTT_BROKER_HOST}")
        # Subscribe to the command topic
        client.subscribe(MQTT_TOPIC_COMMAND, qos=1)
        log.info(f"Subscribed to command topic: {MQTT_TOPIC_COMMAND}")
        # Publish online status
        online_payload = json.dumps({
            "id": JETSON_ID, 
            "id_full": f"jetson-launcher-{JETSON_ID}", 
            "status": "online"
        })
        client.publish(MQTT_TOPIC_STATUS, online_payload, qos=1, retain=True)
    else:
        log.error(f"Failed to connect to MQTT, return code {reason_code}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    log.warning(f"Unexpected disconnection from MQTT Broker. (rc: {reason_code})")

def start_process():
    """Starts the main jetson5.py script."""
    global process_handle
    if process_handle is None or process_handle.poll() is not None:
        try:
            log.info(f"Starting script: {MAIN_SCRIPT_PATH}")
            # Start the main script as a new process
            # We use sys.executable to ensure we're using the same Python interpreter
            process_handle = subprocess.Popen([sys.executable, MAIN_SCRIPT_PATH])
            log.info(f"Process started with PID: {process_handle.pid}")
            return True
        except Exception as e:
            log.error(f"Failed to start process: {e}", exc_info=True)
            return False
    else:
        log.warning(f"Process is already running (PID: {process_handle.pid}). Ignoring start command.")
        return False

def stop_process():
    """Stops the main jetson5.py script."""
    global process_handle
    if process_handle and process_handle.poll() is None:
        try:
            log.info(f"Stopping process with PID: {process_handle.pid}...")
            # Send a SIGTERM signal to allow graceful shutdown
            process_handle.terminate() 
            # Wait for 5 seconds for it to close
            process_handle.wait(timeout=5)
            log.info("Process terminated.")
        except subprocess.TimeoutExpired:
            log.warning("Process did not terminate gracefully. Forcing kill...")
            process_handle.kill() # Force kill
            log.info("Process killed.")
        except Exception as e:
            log.error(f"Error while stopping process: {e}", exc_info=True)
        finally:
            process_handle = None
        return True
    else:
        log.warning("Process is not running. Ignoring stop command.")
        return False

def on_message(client, userdata, msg):
    """Handles incoming commands."""
    global process_handle
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        command = payload.get("command")
        
        log.info(f"Received command: {command}")
        
        if command == "start":
            start_process()
        elif command == "stop":
            stop_process()
        else:
            log.warning(f"Unknown command: {command}")
            
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON received on topic {msg.topic}")
    except Exception as e:
        log.error(f"Error processing command: {e}", exc_info=True)

def main():
    log.info(f"--- Starting Jetson Launcher {JETSON_ID} ---")
    
    # Set up Last Will and Testament (LWT)
    lwt_payload = json.dumps({
        "id": JETSON_ID, 
        "id_full": f"jetson-launcher-{JETSON_ID}", 
        "status": "offline"
    })
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.will_set(MQTT_TOPIC_STATUS, payload=lwt_payload, qos=1, retain=True)

    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        client.loop_forever() # This blocks and handles all MQTT traffic
    except KeyboardInterrupt:
        log.info("Launcher shutting down...")
    except Exception as e:
        log.error(f"FATAL: Could not connect to MQTT broker: {e}")
    finally:
        stop_process() # Ensure the child process is stopped on exit
        client.disconnect()
        log.info("Launcher shut down cleanly.")

if __name__ == "__main__":
    if not os.path.exists(MAIN_SCRIPT_PATH):
        log.error(f"Error: Cannot find main script at: {MAIN_SCRIPT_PATH}")
        sys.exit(1)
    main()

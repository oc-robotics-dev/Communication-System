# Implementation Plan - Long-Range Communication System

## Link Separation Strategy
*   **900 MHz**: Mission-critical control only (low bandwidth, high reliability).
*   **2.4 GHz**: High-bandwidth video (can tolerate packet loss with compression).
*   **Rationale**: Separates critical control from bandwidth-heavy video to ensure drive commands always get through.

---

## Hardware Setup Details

### 1. 2.4 GHz Link (Video/Photos)
*   **Modems**: Microhard pMDDL2450LC.
*   **Wiring**: Ethernet cable -> Raspberry Pi 5.
*   **Power**: **Supply 24V DC externally**. Ethernet does NOT provide power.

### 2. 900 MHz Link Options (Control)

#### **Option A: Connect to Raspberry Pi **
*   **Wiring**: RFD900x -> USB-to-UART Adapter -> Raspberry Pi 5 USB Port.
*   **Pros**: Unified ROS architecture, simple wiring.

#### **Option B: Connect to Arduino Mega **
*   **Power Warning**: **Use an external 5V BEC (Battery Eliminator Circuit)**.
    *   *Why?* The Arduino's 5V pin cannot supply enough current for the radio's transmission spikes (~800mA). Drawing too much will reset the Arduino.
*   **Wiring Detail**:
    *   **RFD900x VCC** -> External 5V Source (NOT Arduino).
    *   **RFD900x GND** -> External GND **AND** Arduino GND (Common Ground).
    *   **RFD900x TX** -> Arduino RX1 (Pin 19).
    *   **RFD900x RX** -> Arduino TX1 (Pin 18).

---

## Architecture Trade-Off Analysis

### **Option A: Connect RFD900x to Raspberry Pi **
*   **Concept**: Radio talks to ROS 2 (Pi), ROS 2 talks to Arduino.
*   **Pros:**
    1.  **Unified Architecture**: Control logic lives in high-level software (ROS). Easy to add autonomy (e.g., obstacle avoidance overrides).
    2.  **Rich Telemetry**: Can send battery levels, GPS, and logs back to ground station.
    3.  **Simple Wiring**: Uses USB. No soldering or voltage level shifting needed.
*   **Cons:**
    1.  **Software Dependency**: If Pi crashes, control is lost.
    2.  **Mitigation**: **MUST** add Watchdog Failsafe to Arduino firmware.

### **Option B: Connect RFD900x to Arduino Mega **
*   **Concept**: Radio talks directly to motor controller.
*   **Pros:**
    1.  **Hardware Safety**: Works even if the Pi/ROS crashes.
*   **Cons:**
    1.  **Split Architecture**: Hard to implement autonomy (Radio fights ROS for control).
    2.  **Complex Wiring**: Requires external 5V power and level shifting logic.
    3.  **Limited Telemetry**: Cannot easily send high-level status back.

---

---

## RF System Integration Strategy (Configuration Only)

This section details how to configure the existing codebase and OS to **recognize and support** the new RF hardware, without touching the control logic yet.

### 1. Hardware Abstraction (OS Level)
We need the OS to provide stable device paths so the software doesn't need to guess.

*   **Serial Port Management (UDEV Rules)**:
    *   **The Problem**: Linux dynamically assigns `/dev/ttyUSB0` or `/dev/ttyACM0` based on plug order. A reboot can swap the Radio and Arduino ports, breaking the system.
    *   **The Solution**: Use Unique Hardware IDs (Vendor/Product ID) to create stable symlinks.
    *   **Configuration File**: `/etc/udev/rules.d/99-rover-serial.rules`
    *   **Abstract Content** (What we will write):
        ```bash
        # Rule 1: Finds the Arduino by its ID (2341:0042) and names it 'arduino'
        SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="arduino"

        # Rule 2: Finds the RFD900x by its ID (0403:6001) and names it 'rfd900'
        SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="rfd900"
        ```
    *   **Strategy**:
        *   `RFD900x` (ID `0403:6001`) -> Symlinked to `/dev/rfd900`
        *   `Arduino` (ID `2341:0042`) -> Symlinked to `/dev/arduino`
    *   **Benefit**: Code can always open `/dev/rfd900` regardless of plug order. It never breaks.

*   **Network Interface Management (Netplan)**:
    *   **Goal**: Ensure the Pi can talk to the Microhard modem (which controls the video link).
    *   **File**: `/etc/netplan/50-cloud-init.yaml`
    *   **Code Overview**:
        ```yaml
        network:
          version: 2
          ethernets:
            eth0:  # The built-in Ethernet port
              dhcp4: no  # Disable auto-IP
              addresses:
                - 192.168.168.10/24  # Static IP / Subnet Mask
              # gateway4: 192.168.168.1  # Optional: If modem is a router
              nameservers:
                addresses: [8.8.8.8, 1.1.1.1] # Optional: If modem has internet
        ```
    *   **How to Apply**: Run `sudo netplan apply` after editing.

### 2. Codebase Configuration (ROS Parameters)
Instead of hardcoding values like `/dev/ttyUSB0` in Python scripts (which is risky if ports change), we will externalize the RF settings.

*   **Centralized Config File**:
    *   **The Problem**: Hardcoding ports (e.g., `SERIAL_PORT = "/dev/ttyACM0"`) means we must edit code to change hardware.
    *   **The Solution**: Use a YAML file to load settings at runtime.
    *   **New File**: `ros/ros2_ws/src/ocrover_controller/config/rover_params.yaml`
    *   **Content**:
        ```yaml
        rfd_bridge:                 # The Node Name
          ros__parameters:
            serial_port: "/dev/rfd900"  # Setting: Where is the radio?
            baud_rate: 57600            # Setting: How fast do we talk?

        subscriber_drive:           # The Node Name (Arduino)
          ros__parameters:
            serial_port: "/dev/arduino" # Setting: Where is the Arduino?
            baud_rate: 9600             # Setting: How fast do we talk?
        ```
    *   **Benefit**: We can change ports or speeds by editing this text file without touching the code.

### 3. Dependency Management
Ensure the environment has the drivers to speak to the hardware.

*   **System Dependencies (`package.xml`)**:
    *   **Action**: Add `<exec_depend>python3-serial</exec_depend>` to `ros/ros2_ws/src/ocrover_controller/package.xml`.
    *   **Reason**: Explicitly declares that this package needs serial communication libraries.

---

## RF Integration Logic (The "Bridge")

**Concept**: The rover ALREADY works wirelessly (over WiFi/DDS). We are simply adding a **second** communication channel (900 MHz Serial).

### 1. The Challenge
*   **Existing WiFi**: Laptop `publisher_drive` -> [WiFi] -> Pi `subscriber_drive` -> Arduino.
*   **New 900 MHz**: Laptop `control_sender` -> [Serial] -> RFD900x -> [Serial] -> Pi.
*   **The Gap**: The Pi receives raw serial bytes (`'w'`, `'a'`), but `subscriber_drive` expects ROS messages (`/cmd_vel`).

### 2. The Solution: `rfd_bridge` Node (Adapter)
We will create a **NEW FILE** to keep things clean. We do not want to messy up the existing code.
*   **File Path**: `ros/ros2_ws/src/ocrover_controller/ocrover_controller/rfd_bridge.py`

#### **Code Overview (Logic):**
```python
class RFDBridge(Node):
    def __init__(self):
        # 1. Get Settings
        self.port = self.get_parameter('serial_port').value
        self.baud = self.get_parameter('baud_rate').value
        
        # 2. Connect to Hardware
        self.serial = serial.Serial(self.port, self.baud)
        
        # 3. Setup ROS Publisher (the "Output")
        self.publisher = self.create_publisher(String, '/cmd_vel', 10)
        
        # 4. Start Reading Loop
        self.timer = self.create_timer(0.01, self.read_serial_loop)

    def read_serial_loop(self):
        if self.serial.in_waiting > 0:
            # A. Read a byte from the Radio
            char = self.serial.read().decode()
            
            # B. Publish it to ROS
            msg = String()
            msg.data = char
            self.publisher.publish(msg)
```
*   **Result**: The existing `subscriber_drive` sees the commands and drives the Arduino. It doesn't know (or care) if the command came from WiFi or Radio.

### 3. Implementation Steps
1.  **Arduino Failsafe**: Update `roverDrive.ino` to stop if ANY link fails.
2.  **Bridge Node**: Develop `rfd_bridge.py` to translate Serial -> ROS.
3.  **Sender Script**: Develop `control_sender.py` to send Serial commands.

---

## Proposed Changes (Software)

### Arduino Firmware (`arduino/roverDrive/`)

#### [MODIFY] [roverDrive.ino](file:///home/quypham/ocr-rover/arduino/roverDrive/roverDrive.ino)
- **Safety Failsafe (CRITICAL)**: Implement a watchdog timer.
- **Logic**: If `millis() - lastCommandTime > 1000` (1 second), force `movementCurrent = "Stop"`.
- **Reason**: Since the radio is on the Pi, if the Pi crashes, the Arduino might keep executing the last "Forward" command forever. This prevents that.

### ROS 2 Workspace (`ros/ros2_ws/`)

#### [NEW] [rfd_bridge.py](file:///home/quypham/ocr-rover/ros/ros2_ws/src/ocrover_controller/ocrover_controller/rfd_bridge.py)
- **Node**: `RFDBridge`
- **Function**: Bidirectional bridge.
    1.  **Control (Rx)**: Reads raw bytes from `/dev/ttyUSBx` (RFD900x) -> Publishes `/cmd_vel`.
    2.  **Telemetry (Tx)**: Subscribes to `/rover_status` (or similar) -> Writes status strings to `/dev/ttyUSBx` (RFD900x) for the Ground Station.
- **Logic**: Maps characters (WASD) -> ROS Drive Messages. Periodically sends heartbeats/status back.

### Ground Station (`ground-station/`)

#### [NEW] [control_sender.py](file:///home/quypham/ocr-rover/ground-station/control_sender.py)
- **Script**: Python script for C2 Laptop using `pyserial`.
- **Function**:
    1.  **Tx**: Captures keyboard input (WASD) -> Sends to RFD900x.
    2.  **Rx**: Listens for incoming Telemetry strings from Rover -> Displays on screen.

## Verification Plan

### Manual Verification
1.  **Failsafe Test (Safety Check)**:
    - Drive rover forward.
    - **Hard Kill**: Unplug the Pi-to-Arduino USB cable while driving.
    - **Expectation**: Arduino detects silence and stops motors within 1 second.
2.  **Radio Control Test**:
    - Run `rfd_bridge` on Pi.
    - Drive via 900MHz from Laptop.
3.  **Video/SSH Test**:
    - Connect via Microhard 2.4GHz.
    - Verify seamless SSH and video stream (no interference with 900MHz control).

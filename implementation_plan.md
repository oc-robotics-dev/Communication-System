# Galaxy RVR - Master Implementation Plan

## Goal
Implement a robust, dual-link communication system for the Galaxy RVR, separating high-bandwidth video/control from critical low-latency telemetry.

## System Architecture: The Two Links

### Link 1: High-Bandwidth (2.4GHz Microhard)
**Purpose**: Video Streaming & PTZ Camera Control.
**Hardware**:
- **Radios**: Microhard pMDDL2450LC (Ethernet Bridge Mode).
- **Camera**: Arducam 12MP PTZ (IMX477 HQ Sensor, IR-Cut Switchable).
- **Interface**: Raspberry Pi Camera Port (CSI) + I2C (GPIO).

**Software Components**:
1.  **`galaxy_camera` Package (New)**:
    - `camera_test.py`: Standalone script to verify video capture and save images (URC requirement).
    - `video_publisher.py`: Captures frames from `/dev/video0`, publishes to `/camera/image_raw` (compressed).
    - `ptz_controller.py`: Subscribes to `/cmd_ptz`, controls servos via I2C (Address `0x0C` or `0x40`).

### Link 2: Low-Bandwidth / Long-Range (900MHz RFD900x)
**Purpose**: Critical Telemetry, Drive Control, Failsafe.
**Hardware**:
- **Radios**: RFD900x-US (Serial via USB/UART).
- **Drive System**: Arduino Uno/Nano + Motor Driver.

**Software Components**:
1.  **`subscriber_drive.py` (Modify)**:
    - Upgrade to send **Heartbeat Packets** at 10Hz.
    - Protocol: `<H, SPEED, TURN, CHECKSUM>` (ASCII).
2.  **`roverGalaxyDriver.ino` (Modify)**:
    - Implement packet parser with start/end markers `< >`.
    - **Failsafe**: Stop motors if no valid packet received for 500ms.

### 3. Computer Vision Strategy (Future Implementation)
**Goal**: Reliable detection of mission objects using CPU-based OpenCV (No Neural Networks).

#### A. Orange Mallet
- **Features**: Distinctive Orange Color, Shape.
- **Algorithm**:
    1.  **Color Threshold**: HSV Range (Approx `[10, 150, 150]` - `[25, 255, 255]`).
    2.  **Noise Removal**: Morphological Open/Close to remove wires/glare.
    3.  **Shape Filter**: Aspect Ratio (must be elongated, <0.3 or >3.0) and Solidity (solid shape).

#### B. Rock Pick Hammer
- **Features**: Metallic Head, Black/Blue Handle, "T" or "L" Shape.
- **Algorithm**:
    1.  **ROI Focus**: Detect the Handle (Dark Blue/Black threshold).
    2.  **Shape Verification**: Long rectangular aspect ratio (~1:4).
    3.  **Context**: Search for high-contrast/metallic pixels (Head) connected to the handle region.

#### C. Water Bottle
- **Features**: Transparent, 1L Wide-Mouth, Vertical cylindrical edges.
- **Algorithm**:
    1.  **Edge Detection**: Sobel-X or Canny to find vertical edges.
    2.  **Contour Analysis**: Group vertical edges.
    3.  **Aspect Ratio**: Check for ~2.4:1 Height/Width ratio (Generic 1L bottle dimensions).


---

## Technical Appendix: Installation Guide

### Hardware Setup
- **Camera**: Connect CSI ribbon cable. Connect PTZ HAT (I2C SDA/SCL, 5V, GND).
- **Radios**:
    - **Microhard**: Configured as Transparent Bridge (Ethernet).
    - **RFD900x**: Configured at 57600 baud (USB/UART).

### Software Environment
- **OS**: Ubuntu 24.04 LTS (Noble Numbat).
- **ROS 2**: Jazzy Jalisco.
- **Dependencies**: `python3-opencv`, `ros-jazzy-cv-bridge`, `ros-jazzy-vision-opencv`, `i2c-tools`, `python3-smbus`.

## Verification Plan

### Automated Tests
- None for this phase.

### Manual Verification
- **Camera Test**: Run `python3 camera_test.py`. Verify feed window opens. Press 's' to save an image and verify it exists on disk.


# Galaxy RVR - Vision

## Problem
- **Unreliable Communication**: High-bandwidth video data interferes with critical low-latency telemetry control signals on shared links.
- **Lack of Failsafes**: The current drive system risks runaway behavior if the connection drops, posing safety hazards.
- **Complex Integration**: Merging diverse hardware (Raspberry Pi, Arduino, Microhard, RFD900x) into a cohesive ROS 2 system is error-prone without a clear architecture.

## Target Users / Use Cases
- **Remote Operators**: Require low-latency video feedback and precise, responsive controls for teleoperation in challenging environments.
- **Robotics Developers**: Need a modular, documented ROS 2 codebase (Jazzy/Ubuntu 24.04) that is easy to extend and debug.
- **Field Researchers**: Depend on a ruggedized communication link that separates critical control from high-bandwidth sensor data.

## Constraints & Assumptions
- **Dual-Link Architecture**: Must strictly separate video/PTZ (2.4GHz Microhard Ethernet bridge) from drive control (900MHz RFD900x Serial/UART).
- **Hardware Stack**: Fixed hardware including Arducam 5MP PTZ, Raspberry Pi 4/5, Arduino Uno/Nano, and specific radio modules.
- **Software Environment**: Strict adherence to ROS 2 Jazzy on Ubuntu 24.04 LTS; Python for ROS nodes, C++ for Arduino firmware.
- **Safety First**: The drive system must implement a hardware-level failsafe (e.g., auto-stop after 500ms signal loss).

## Success Criteria
- **Stable Video Stream**: Continuous, low-latency video feed accessible via ROS topics over the 2.4GHz link.
- **Responsive Control**: PTZ and Drive commands execute with imperceptible delay; drive commands are robust to video bandwidth saturation.
- **Verified Failsafe**: The rover automatically halts drive motors within 500ms of telemetry link loss.
- **Reproducible Build**: A documented installation process allows a new developer to set up the full stack from a fresh OS install.

## System Tasks (URC)

### RF / Communications
- Provide a reliable wireless link between rover and command station for all tasks (no tether).
- Support real-time teleoperation (drive, arm, tools) with low enough latency that operators can safely maneuver.
- Transmit telemetry (pose, system health, battery, fault states) continuously to the command station.
- Carry video streams from onboard cameras to the operators for navigation and task execution.
- Allow operators to reconfigure links/channels between tasks to match URC-assigned frequencies and avoid interference.
- Detect loss of comms and trigger a defined safe behavior (e.g., stop motors, hold arm, signal fault).

### Camera / Perception
- Provide at least one forward-facing navigation camera for driving and obstacle avoidance.
- Provide additional task cameras (pan-tilt or zoom if possible) to inspect samples, tools, and markers at close range.
- Support capturing still images of specified targets (e.g., science sites, equipment, markers) on operator command.
- Enable operators to identify objects/markers required by URC tasks (e.g., tools to pick up, panels to inspect, sample locations).
- Record or stream video with sufficient resolution and stability that judges can verify task completion from the footage.

## Business Logic

### Core Use Cases
- **Teleoperate the Rover**: An operator sends speed and turn commands from a base station; the rover receives them over the 900 MHz link and drives its motors accordingly.
- **Monitor Live Video**: An operator views a continuous camera feed streamed from the rover over the 2.4 GHz link while teleoperating.
- **Adjust Camera Angle**: An operator sends pan/tilt/zoom commands; the rover's camera repositions in near-real-time over the 2.4 GHz link.
- **Automatic Safe Stop**: If the telemetry link is lost, the rover stops all motor activity on its own within a bounded time window.

### Domain Rules & Constraints
- **Link Separation**: Drive/telemetry traffic must never share the same radio link as video traffic; the two links are physically and logically independent.
- **Heartbeat Required**: The base station must continuously send periodic heartbeat packets to the rover; silence is treated as a lost connection.
- **Motor Speed Ceiling**: Motor PWM output must never exceed the configured maximum (currently 50 out of 255) to protect the drivetrain.
- **Failsafe Timeout**: If the rover firmware receives no valid command packet within 500 ms, it must cut power to all drive motors.
- **Packet Integrity**: Every drive command packet must include a checksum; the rover firmware must discard packets that fail validation.
- **Latency Budget**: End-to-end drive command latency must be low enough for safe maneuvering (target < 100 ms; exact budget TODO: measure and confirm on hardware).
- **Video-Link-Down Behavior**: If the video link drops but telemetry remains healthy, the rover continues accepting drive commands; the operator is alerted via telemetry and decides whether to stop.

### Data Flows
- **Drive Command Path**: Operator input → base-station ROS 2 node publishes a direction topic → drive subscriber node converts the topic into a framed serial packet → packet is transmitted over 900 MHz radio → Arduino firmware parses the packet and sets motor pins.
- **Heartbeat Path**: Drive subscriber node emits a periodic heartbeat packet over serial at 10 Hz → Arduino firmware resets its watchdog timer on each valid packet → if the timer expires (500 ms), firmware triggers a safe stop.
- **Video Path**: On-board camera captures frames → a ROS 2 camera node publishes compressed images to a topic → the topic is transported over the 2.4 GHz Ethernet bridge to the base station for display.
- **PTZ Command Path**: Operator sends a PTZ command topic → a ROS 2 PTZ node on the rover receives it over the 2.4 GHz link → the node writes to the camera's servo controller via I2C.
- **Telemetry Return Path**: Rover transmits pose, system health, battery state, and fault flags back to the base station continuously over the 900 MHz link (exact message format TODO: define).

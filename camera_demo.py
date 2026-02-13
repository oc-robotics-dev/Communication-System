#!/usr/bin/env python3
"""Galaxy RVR — Camera Demo (Pi 5 / SSH-friendly).

A clean, modular script for:
1.  Live Video Streaming (MJPEG over HTTP).
2.  Image Capture.
3.  Autonomy/Vision Framework (Structure for URC Mission).

Usage:
    python3 camera_demo.py              # Capture single photo
    python3 camera_demo.py --stream     # Live stream
    python3 camera_demo.py --autonomy   # Live stream + Vision Overlay
"""

import os
import sys
import time
import argparse
import subprocess
import threading
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple, Dict, Any

import cv2
import numpy as np

# Try importing ArUco (Robust fallback if missing)
try:
    from cv2 import aruco
    ARUCO_AVAILABLE = True
except ImportError:
    ARUCO_AVAILABLE = False


# ── Configuration ──────────────────────────────────────────────
CONFIG = {
    "save_dir": os.path.expanduser("~/galaxy_captures"),
    "width": 640,
    "height": 480,
    "fps": 30,
    "port": 8080,
    "camera_cmd": ["rpicam-vid", "-t", "0", "--codec", "mjpeg", "-o", "-", "-n"]
}

# Setup Logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("GalaxyRVR")


# ── Autonomy / Computer Vision System ──────────────────────────
class VisionSystem:
    """
    Modular Computer Vision System for Galaxy RVR.
    
    Responsibilities:
    - ArUco Tag Detection (Navigation)
    - Object Detection (Mallet, Hammer, Bottle)
    - Status Overlay (OSD)
    """
    
    def __init__(self):
        self.frame_count = 0
        self.mode = "TELEOP"
        self.latest_detections = []
        
        # Initialize ArUco
        if ARUCO_AVAILABLE:
            self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
            self.aruco_params = aruco.DetectorParameters()
            self.detector = aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        else:
            logger.warning("cv2.aruco not found. Tag detection disabled.")

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Main pipeline: Input Frame -> Process -> Output Frame with Overlay."""
        self.frame_count += 1
        
        # 1. Detect Navigation Markers (ArUco)
        self.detect_aruco(frame)
        
        # 2. Detect Science Objects (Placeholders)
        self.detect_mallet(frame)
        self.detect_hammer(frame)
        self.detect_bottle(frame)
        
        # 3. Draw UI/Overlay
        self.draw_overlay(frame)
        
        return frame

    def detect_aruco(self, frame: np.ndarray):
        """Detect and draw ArUco tags."""
        if not ARUCO_AVAILABLE:
            return

        corners, ids, _ = self.detector.detectMarkers(frame)
        if ids is not None:
            aruco.drawDetectedMarkers(frame, corners, ids)
            # Logic for "Target Reached" could involve distance estimation here
            # e.g. if corner area > threshold -> Reached
            self.latest_detections.append(f"Tag IDs: {ids.flatten()}")

    def detect_mallet(self, frame: np.ndarray):
        """
        TODO: Implement robust Orange Mallet detection.
        Strategy: HSV Range (Orange) + Morphological Ops + Aspect Ratio Filter.
        """
        pass

    def detect_hammer(self, frame: np.ndarray):
        """
        TODO: Implement Rock Pick Hammer detection.
        Strategy: Dark Blue/Black Handle detection + Shape Analysis.
        """
        pass

    def detect_bottle(self, frame: np.ndarray):
        """
        TODO: Implement Water Bottle detection.
        Strategy: Vertical Edge Detection (Sobel) + Aspect Ratio (2.4:1).
        """
        pass

    def draw_overlay(self, frame: np.ndarray):
        """Draw status, mode, and detections on the frame."""
        # Top Bar Background
        cv2.rectangle(frame, (0, 0), (CONFIG["width"], 40), (0, 0, 0), -1)
        
        # Mode Indicator
        color = (0, 255, 0) # Green
        cv2.circle(frame, (20, 20), 8, color, -1)
        cv2.putText(frame, f"MODE: {self.mode}", (40, 28), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Detection List
        if self.latest_detections:
            msg = " | ".join(self.latest_detections)
            cv2.putText(frame, msg, (200, 28), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Reset detections for next frame
        self.latest_detections = []


# ── Web Streaming ──────────────────────────────────────────────
class MJPEGStreamHandler(BaseHTTPRequestHandler):
    """Serve camera stream via HTTP MJPEG."""
    
    frame_lock = threading.Lock()
    current_frame = None
    
    def log_message(self, format, *args):
        return  # Suppress HTTP logs

    def do_GET(self):
        routes = {
            '/': self.serve_html,
            '/stream': self.serve_stream,
            '/capture': self.serve_capture
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)

    def serve_html(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        html = f"""
        <!DOCTYPE html><html><head><title>Galaxy RVR Vision</title></head>
        <body style="background:#111; color:#eee; text-align:center; font-family:sans-serif;">
            <h2>Galaxy RVR Vision Feed</h2>
            <img src="/stream" style="border:2px solid #333; max-width:100%;">
            <p>
                <a href="/capture" style="color:#0f0; text-decoration:none;">[ Save Photo ]</a>
            </p>
        </body></html>
        """
        self.wfile.write(html.encode())

    def serve_stream(self):
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()
        try:
            while True:
                with self.frame_lock:
                    if self.current_frame is None:
                        time.sleep(0.01)
                        continue
                    frame = self.current_frame
                
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
                time.sleep(1.0 / CONFIG["fps"])
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_capture(self):
        os.makedirs(CONFIG["save_dir"], exist_ok=True)
        with self.frame_lock:
            frame = self.current_frame
        
        if frame:
            filename = os.path.join(CONFIG["save_dir"], f"capture_{datetime.now():%Y%m%d_%H%M%S}.jpg")
            with open(filename, 'wb') as f:
                f.write(frame)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Saved: {filename}".encode())
        else:
            self.send_error(503, "No frame available")


def frame_reader(process, vision_system: Optional[VisionSystem]):
    """Reads raw MJPEG from process stdout, decodes, processes (optional), and updates buffer."""
    buffer = b''
    while True:
        chunk = process.stdout.read(4096)
        if not chunk: break
        buffer += chunk
        
        while True:
            start = buffer.find(b'\xff\xd8')
            end = buffer.find(b'\xff\xd9', start + 2) if start != -1 else -1
            
            if start != -1 and end != -1:
                jpg_data = buffer[start:end+2]
                buffer = buffer[end+2:]
                
                # Autonomy Processing Hook
                if vision_system:
                    try:
                        # Decode -> Process -> Encode (Adds latency but enables OSD)
                        img = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            img = vision_system.process_frame(img)
                            _, encoded = cv2.imencode('.jpg', img)
                            jpg_data = encoded.tobytes()
                    except Exception as e:
                        logger.error(f"Vision error: {e}")
                
                with MJPEGStreamHandler.frame_lock:
                    MJPEGStreamHandler.current_frame = jpg_data
            else:
                break


def start_stream(autonomy: bool):
    """Initializes camera process and web server."""
    cmd = CONFIG["camera_cmd"] + [
        "--width", str(CONFIG["width"]),
        "--height", str(CONFIG["height"]),
        "--framerate", str(CONFIG["fps"])
    ]
    
    logger.info(f"Starting Camera: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for startup
    time.sleep(1)
    if process.poll() is not None:
        logger.error(f"Camera failed: {process.stderr.read().decode()}")
        return

    # Initialize Vision System if requested
    vision = VisionSystem() if autonomy else None
    if vision: 
        logger.info("Vision System: ENABLED")

    # Start Frame Reader Thread
    t = threading.Thread(target=frame_reader, args=(process, vision), daemon=True)
    t.start()

    # Start Web Server
    try:
        server = HTTPServer(('0.0.0.0', CONFIG["port"]), MJPEGStreamHandler)
        local_ip = "0.0.0.0" # Simplification
        logger.info(f"Stream available at http://{local_ip}:{CONFIG['port']}/stream")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        process.terminate()
        server.server_close()


# ── Main Entry ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Galaxy RVR Camera Controller")
    parser.add_argument("--stream", action="store_true", help="Start MJPEG Stream")
    parser.add_argument("--autonomy", action="store_true", help="Enable Vision System")
    args = parser.parse_args()

    if args.stream or args.autonomy:
        start_stream(args.autonomy)
    else:
        # Simple Capture Mode (subprocess wrapper)
        filename = os.path.join(CONFIG["save_dir"], f"capture_{datetime.now():%Y%m%d_%H%M%S}.jpg")
        os.makedirs(CONFIG["save_dir"], exist_ok=True)
        subprocess.run(["rpicam-still", "-o", filename, "-n", "-t", "1000", 
                        "--width", str(CONFIG["width"]), "--height", str(CONFIG["height"])])
        logger.info(f"Photo saved: {filename}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
aurad - Aura Biometric Authentication Daemon
Runs as systemd service, handles camera + ONNX inference, communicates via Unix socket
"""

import os
import sys
import socket
import struct
import threading
import logging
import signal
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

# Configuration - use local paths for development, install-time paths for production
import os
IS_DEV = os.getenv("AURA_DEV", "1") == "1"

if IS_DEV:
    BASE_DIR = Path("/home/anmol/Projects/Aura")
    SOCKET_PATH = str(BASE_DIR / "run/aura.sock")
    MODEL_DIR = BASE_DIR / "models"
    PROFILES_DIR = BASE_DIR / "profiles"
    LOG_FILE = str(BASE_DIR / "logs/aurad.log")
else:
    SOCKET_PATH = "/run/aura/aura.sock"
    MODEL_DIR = Path("/usr/share/aura/models")
    PROFILES_DIR = Path("/var/lib/aura/profiles")
    LOG_FILE = "/var/log/aura/aurad.log"

FACE_MODEL = MODEL_DIR / "mobilefacenet.onnx"
LIVENESS_MODEL = MODEL_DIR / "minifasnet.onnx"

AUTH_SUCCESS = b"\x01"
AUTH_FAILURE = b"\x00"

# Cosine similarity threshold for face verification
VERIFICATION_THRESHOLD = 0.6
LIVENESS_THRESHOLD = 0.7

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("aurad")


class FaceDetector:
    """Face detection using OpenCV DNN (lightweight)"""
    def __init__(self):
        # Use OpenCV's built-in face detector (Ultralight/MediaPipe style)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        # Try to use a more modern DNN detector if available
        self.use_dnn = False
        try:
            model_path = MODEL_DIR / "face_detector.pb"
            config_path = MODEL_DIR / "face_detector.pbtxt"
            if model_path.exists() and config_path.exists():
                self.dnn_net = cv2.dnn.readNetFromTensorflow(str(model_path), str(config_path))
                self.use_dnn = True
        except Exception:
            pass

    def detect(self, frame):
        """Detect faces, return list of (x, y, w, h)"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return faces


class ONNXInference:
    """ONNX Runtime inference wrapper for face verification and liveness"""
    def __init__(self):
        self.face_session = None
        self.liveness_session = None
        self._load_models()

    def _load_models(self):
        providers = ['CPUExecutionProvider']
        # Try to enable OpenVINO if available
        try:
            providers.insert(0, 'OpenVINOExecutionProvider')
        except Exception:
            pass

        if FACE_MODEL.exists():
            self.face_session = ort.InferenceSession(str(FACE_MODEL), providers=providers)
            self.face_input_name = self.face_session.get_inputs()[0].name
            self.face_output_name = self.face_session.get_outputs()[0].name
            logger.info(f"Loaded face model: {FACE_MODEL}")
        else:
            logger.warning(f"Face model not found at {FACE_MODEL}")

        if LIVENESS_MODEL.exists():
            self.liveness_session = ort.InferenceSession(str(LIVENESS_MODEL), providers=providers)
            self.liveness_input_name = self.liveness_session.get_inputs()[0].name
            self.liveness_output_name = self.liveness_session.get_outputs()[0].name
            logger.info(f"Loaded liveness model: {LIVENESS_MODEL}")
        else:
            logger.warning(f"Liveness model not found at {LIVENESS_MODEL}")

    def get_embedding(self, face_img):
        """Extract 512-d embedding from face image (112x112)"""
        if self.face_session is None:
            return None

        # Preprocess: resize to 112x112, normalize to [-1, 1]
        face_resized = cv2.resize(face_img, (112, 112))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        face_normalized = (face_rgb.astype(np.float32) - 127.5) / 127.5
        face_transposed = np.transpose(face_normalized, (2, 0, 1))
        face_batch = np.expand_dims(face_transposed, axis=0)

        outputs = self.face_session.run([self.face_output_name], {self.face_input_name: face_batch})
        embedding = outputs[0].flatten()
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def check_liveness(self, face_img):
        """Run liveness detection (anti-spoofing)"""
        if self.liveness_session is None:
            # No liveness model - assume live for testing
            return True, 1.0

        # Preprocess for MiniFASNet (typically 80x80 or similar)
        face_resized = cv2.resize(face_img, (80, 80))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        face_normalized = face_rgb.astype(np.float32) / 255.0
        face_transposed = np.transpose(face_normalized, (2, 0, 1))
        face_batch = np.expand_dims(face_transposed, axis=0)

        outputs = self.liveness_session.run([self.liveness_output_name], {self.liveness_input_name: face_batch})
        # MiniFASNet outputs: [real_score, fake_score] or similar
        scores = outputs[0].flatten()
        if len(scores) >= 2:
            real_score = scores[0] / (scores[0] + scores[1] + 1e-8)
        else:
            real_score = float(scores[0])

        is_live = real_score > LIVENESS_THRESHOLD
        return is_live, real_score


class ProfileManager:
    """Manage enrolled user face profiles"""
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True, mode=0o750)

    def get_profile_path(self, username):
        return PROFILES_DIR / f"{username}.npy"

    def save_profile(self, username, embedding):
        """Save face embedding for user"""
        path = self.get_profile_path(username)
        np.save(path, embedding)
        path.chmod(0o600)
        logger.info(f"Saved profile for {username}")

    def load_profile(self, username):
        """Load face embedding for user"""
        path = self.get_profile_path(username)
        if path.exists():
            return np.load(path)
        return None

    def delete_profile(self, username):
        """Delete user profile"""
        path = self.get_profile_path(username)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted profile for {username}")

    def list_profiles(self):
        """List all enrolled users"""
        return [p.stem for p in PROFILES_DIR.glob("*.npy")]


class CameraManager:
    """Camera management with V4L2"""
    def __init__(self, device_index=0):
        self.device_index = device_index
        self.cap = None
        self._find_camera()

    def _find_camera(self):
        """Find the best available camera (prefer IR)"""
        for i in range(4):
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                # Check if it's an IR camera by reading format
                fourcc = cap.get(cv2.CAP_PROP_FOURCC)
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                logger.info(f"Camera {i}: {width}x{height} fourcc={int(fourcc)}")
                cap.release()

        # Use specified or first available
        self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.device_index}")

        # Set properties for speed
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read_frame(self):
        """Read a frame, return (success, frame)"""
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class AuraDaemon:
    def __init__(self):
        self.running = False
        self.server_socket = None
        self.face_detector = FaceDetector()
        self.inference = ONNXInference()
        self.profiles = ProfileManager()
        self.camera = None

        # Stats
        self.auth_attempts = 0
        self.auth_successes = 0

    def initialize(self):
        """Initialize all components"""
        logger.info("Initializing Aura daemon...")
        try:
            self.camera = CameraManager()
            logger.info("Camera initialized")
        except Exception as e:
            logger.error(f"Camera init failed: {e}")
            return False

        # Verify models loaded
        if self.inference.face_session is None:
            logger.error("Face verification model not loaded!")
            return False

        logger.info("Aura daemon initialized successfully")
        return True

    def verify_user(self, username):
        """Main verification flow: capture -> detect -> liveness -> verify"""
        logger.info(f"Verification request for user: {username}")

        # Load enrolled profile
        enrolled_embedding = self.profiles.load_profile(username)
        if enrolled_embedding is None:
            logger.warning(f"No enrolled profile for {username}")
            return False

        # Capture frames with timeout
        start_time = time.time()
        max_duration = 5.0  # 5 second timeout
        best_similarity = 0.0
        liveness_passed = False

        while time.time() - start_time < max_duration:
            ret, frame = self.camera.read_frame()
            if not ret:
                time.sleep(0.05)
                continue

            # Detect faces
            faces = self.face_detector.detect(frame)
            if len(faces) == 0:
                continue

            # Use largest face
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            face_img = frame[y:y+h, x:x+w]

            # Liveness check
            is_live, live_score = self.inference.check_liveness(face_img)
            if is_live:
                liveness_passed = True
                logger.debug(f"Liveness passed: {live_score:.3f}")

                # Face verification
                embedding = self.inference.get_embedding(face_img)
                if embedding is not None:
                    # Cosine similarity
                    similarity = np.dot(enrolled_embedding, embedding)
                    best_similarity = max(best_similarity, similarity)
                    logger.debug(f"Similarity: {similarity:.3f}")

                    if similarity > VERIFICATION_THRESHOLD and liveness_passed:
                        logger.info(f"Verification SUCCESS for {username}: sim={similarity:.3f}")
                        return True

            time.sleep(0.05)  # ~20 FPS processing

        logger.info(f"Verification FAILED for {username}: best_sim={best_similarity:.3f}, live={liveness_passed}")
        return False

    def handle_client(self, conn, addr):
        """Handle a single client connection"""
        try:
            # Read username (null-terminated or newline)
            data = b""
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data or b"\x00" in data:
                    break

            username = data.decode("utf-8").strip("\n\x00")
            if not username:
                conn.sendall(AUTH_FAILURE)
                return

            # Verify
            result = self.verify_user(username)
            conn.sendall(AUTH_SUCCESS if result else AUTH_FAILURE)

        except Exception as e:
            logger.error(f"Client handler error: {e}")
            conn.sendall(AUTH_FAILURE)
        finally:
            conn.close()

    def run(self):
        """Main daemon loop"""
        if not self.initialize():
            logger.error("Initialization failed, exiting")
            return 1

        # Clean up old socket
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        # Ensure socket directory exists
        os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)

        # Create Unix socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o666)  # Allow all users to connect
        self.server_socket.listen(5)

        self.running = True
        logger.info(f"Aura daemon listening on {SOCKET_PATH}")

        # Signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Main loop
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                conn, addr = self.server_socket.accept()
                # Handle each client in a thread for concurrently
                thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

        # Cleanup
        self.server_socket.close()
        try:
            os.unlink(SOCKET_PATH)
        except Exception:
            pass
        if self.camera:
            self.camera.release()
        logger.info("Aura daemon stopped")
        return 0


def main():
    # Ensure we're root (needed for PAM integration and camera access)
    if os.geteuid() != 0 and not IS_DEV:
        logger.error("Aura daemon must run as root")
        return 1

    daemon = AuraDaemon()
    return daemon.run()


if __name__ == "__main__":
    sys.exit(main())
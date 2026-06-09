#!/usr/bin/env python3
"""
Enrollment script for Aura - captures face and saves embedding
"""

import os
import sys
import time
import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path

# Use dev paths
BASE_DIR = Path("/home/anmol/Projects/Aura")
MODEL_DIR = BASE_DIR / "models"
PROFILES_DIR = BASE_DIR / "profiles"
FACE_MODEL = MODEL_DIR / "mobilefacenet.onnx"

PROFILES_DIR.mkdir(parents=True, exist_ok=True)

VERIFICATION_THRESHOLD = 0.6


class FaceDetector:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return faces


class InferenceEngine:
    def __init__(self):
        self.session = ort.InferenceSession(str(FACE_MODEL), providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def get_embedding(self, face_img):
        face_resized = cv2.resize(face_img, (112, 112))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        face_normalized = (face_rgb.astype(np.float32) - 127.5) / 127.5
        face_transposed = np.transpose(face_normalized, (2, 0, 1))
        face_batch = np.expand_dims(face_transposed, axis=0)

        outputs = self.session.run([self.output_name], {self.input_name: face_batch})
        embedding = outputs[0].flatten()
        embedding = embedding / np.linalg.norm(embedding)
        return embedding


def enroll_user(username):
    """Capture face and save embedding for user"""
    print(f"Enrolling user: {username}")
    print("Look at the camera. Press 'q' to quit without saving.")

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    detector = FaceDetector()
    engine = InferenceEngine()

    best_embedding = None
    best_quality = 0
    samples_needed = 5
    samples_collected = 0

    print(f"Collecting {samples_needed} good samples...")

    while samples_collected < samples_needed:
        ret, frame = cap.read()
        if not ret:
            continue

        faces = detector.detect(frame)
        if len(faces) == 0:
            cv2.putText(frame, "No face detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("Enrollment - Press 'q' to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        # Use largest face
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_img = frame[y:y+h, x:x+w]

        # Get embedding
        embedding = engine.get_embedding(face_img)
        if embedding is not None:
            # Quality = face size (larger = better)
            quality = w * h
            if quality > best_quality:
                best_quality = quality
                best_embedding = embedding

            samples_collected += 1
            print(f"  Sample {samples_collected}/{samples_needed} - Quality: {quality}")

        # Draw rectangle
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, f"Sample {samples_collected}/{samples_needed}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Enrollment - Press 'q' to quit", frame)

        if cv2.waitKey(100) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if best_embedding is not None:
        # Save profile
        profile_path = PROFILES_DIR / f"{username}.npy"
        np.save(profile_path, best_embedding)
        profile_path.chmod(0o600)
        print(f"Enrolled successfully! Profile saved to {profile_path}")
        return True
    else:
        print("Enrollment failed - no valid face detected")
        return False


def list_users():
    """List enrolled users"""
    users = [p.stem for p in PROFILES_DIR.glob("*.npy")]
    if users:
        print("Enrolled users:")
        for u in users:
            print(f"  - {u}")
    else:
        print("No users enrolled")


def delete_user(username):
    """Delete user profile"""
    profile_path = PROFILES_DIR / f"{username}.npy"
    if profile_path.exists():
        profile_path.unlink()
        print(f"Deleted profile for {username}")
    else:
        print(f"No profile found for {username}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python enroll.py enroll <username>  - Enroll a new user")
        print("  python enroll.py list               - List enrolled users")
        print("  python enroll.py delete <username>  - Delete a user")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "enroll":
        if len(sys.argv) < 3:
            print("Usage: python enroll.py enroll <username>")
            sys.exit(1)
        enroll_user(sys.argv[2])

    elif cmd == "list":
        list_users()

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("Usage: python enroll.py delete <username>")
            sys.exit(1)
        delete_user(sys.argv[2])

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
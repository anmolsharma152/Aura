#!/usr/bin/env python3
"""
Download ONNX models for Aura face verification and liveness detection.
Models are sourced from public repositories and converted to ONNX format.
"""

import os
import sys
import urllib.request
from pathlib import Path

# Use dev paths when AURA_DEV is set
if os.getenv("AURA_DEV", "1") == "1":
    BASE_DIR = Path("/home/anmol/Projects/Aura")
    MODEL_DIR = BASE_DIR / "models"
else:
    MODEL_DIR = Path("/usr/share/aura/models")

MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Model URLs (these are example URLs - actual models need to be sourced)
# MobileFaceNet ONNX models can be found in various repositories
MODELS = {
    "mobilefacenet.onnx": {
        "url": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "description": "MobileFaceNet face recognition model (from InsightFace buffalo_l)",
        "note": "Need to extract from buffalo_l.zip - contains w600k_r50.onnx which can be used"
    },
    "minifasnet.onnx": {
        "url": "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/releases/download/v1.0/minifasnet.onnx",
        "description": "MiniFASNet liveness detection model",
        "note": "Direct download from Silent-Face-Anti-Spoofing repo"
    }
}

# Alternative: Use publicly available ONNX models
ALTERNATIVE_MODELS = {
    "mobilefacenet.onnx": [
        "https://github.com/onnx/models/raw/main/vision/body_analysis/arcface/model/arcface-resnet100.onnx",
        "https://huggingface.co/onnx-community/mobilefacenet/resolve/main/mobilefacenet.onnx",
    ],
    "minifasnet.onnx": [
        "https://huggingface.co/onnx-community/minifasnet/resolve/main/minifasnet.onnx",
    ]
}


def download_file(url, dest_path):
    """Download a file with progress"""
    try:
        print(f"Downloading {url} -> {dest_path}")
        urllib.request.urlretrieve(url, dest_path)
        print(f"Downloaded: {dest_path}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def download_mobilefacenet_from_insightface():
    """Download and extract MobileFaceNet from InsightFace"""
    import zipfile
    import tempfile

    url = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
    zip_path = MODEL_DIR / "buffalo_l.zip"

    if download_file(url, zip_path):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(MODEL_DIR)
            # The model we want is typically w600k_r50.onnx or similar
            for f in MODEL_DIR.glob("*.onnx"):
                if "r50" in f.name or "mobileface" in f.name.lower():
                    target = MODEL_DIR / "mobilefacenet.onnx"
                    f.rename(target)
                    print(f"Extracted and renamed to {target}")
                    return True
            print("Could not find suitable model in archive")
        except Exception as e:
            print(f"Extraction failed: {e}")
    return False


def create_placeholder_models():
    """Create dummy ONNX models for testing without real models"""
    import onnx
    import onnx.numpy_helper as nh
    import numpy as np

    print("Creating placeholder ONNX models for testing...")

    # Create dummy MobileFaceNet-like model (input: 1x3x112x112, output: 1x512)
    dummy_face_onnx = MODEL_DIR / "mobilefacenet.onnx"
    if not dummy_face_onnx.exists():
        # Simple identity-like model for testing
        import onnx.helper as helper
        from onnx import TensorProto

        X = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 3, 112, 112])
        Y = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 512])

        # Just a simple conv + pool + fc to make it valid
        nodes = [
            helper.make_node('Conv', ['input', 'W1', 'B1'], ['conv1'],
                           kernel_shape=[3, 3], pads=[1, 1, 1, 1]),
            helper.make_node('Relu', ['conv1'], ['relu1']),
            helper.make_node('GlobalAveragePool', ['relu1'], ['pool1']),
            helper.make_node('Reshape', ['pool1', 'shape1'], ['output']),
        ]

        # Create dummy weights
        W1 = nh.from_array(np.random.randn(64, 3, 3, 3).astype(np.float32), name='W1')
        B1 = nh.from_array(np.zeros(64, dtype=np.float32), name='B1')
        shape1 = nh.from_array(np.array([1, 512], dtype=np.int64), name='shape1')

        graph = helper.make_graph(nodes, 'MobileFaceNet', [X], [Y], [W1, B1, shape1])
        model = helper.make_model(graph, producer_name='Aura-placeholder')
        onnx.save(model, str(dummy_face_onnx))
        print(f"Created placeholder: {dummy_face_onnx}")

    # Create dummy MiniFASNet-like model (input: 1x3x80x80, output: 1x2)
    dummy_live_onnx = MODEL_DIR / "minifasnet.onnx"
    if not dummy_live_onnx.exists():
        import onnx.helper as helper
        from onnx import TensorProto

        X = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 3, 80, 80])
        Y = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 2])

        nodes = [
            helper.make_node('Conv', ['input', 'W1', 'B1'], ['conv1'],
                           kernel_shape=[3, 3], pads=[1, 1, 1, 1]),
            helper.make_node('Relu', ['conv1'], ['relu1']),
            helper.make_node('GlobalAveragePool', ['relu1'], ['pool1']),
            helper.make_node('Reshape', ['pool1', 'shape1'], ['output']),
        ]

        W1 = nh.from_array(np.random.randn(16, 3, 3, 3).astype(np.float32), name='W1')
        B1 = nh.from_array(np.zeros(16, dtype=np.float32), name='B1')
        shape1 = nh.from_array(np.array([1, 2], dtype=np.int64), name='shape1')

        graph = helper.make_graph(nodes, 'MiniFASNet', [X], [Y], [W1, B1, shape1])
        model = helper.make_model(graph, producer_name='Aura-placeholder')
        onnx.save(model, str(dummy_live_onnx))
        print(f"Created placeholder: {dummy_live_onnx}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download Aura ONNX models")
    parser.add_argument("--placeholder", action="store_true", help="Create placeholder models for testing")
    parser.add_argument("--insightface", action="store_true", help="Download from InsightFace (buffalo_l)")
    args = parser.parse_args()

    if args.placeholder:
        try:
            create_placeholder_models()
            print("Placeholder models created successfully")
            return 0
        except Exception as e:
            print(f"Failed to create placeholders: {e}")
            return 1

    if args.insightface:
        if download_mobilefacenet_from_insightface():
            print("MobileFaceNet downloaded from InsightFace")
        else:
            print("Failed to download from InsightFace")
        # MiniFASNet would need separate handling
        return 0

    # Try alternative sources
    print("Attempting to download models from alternative sources...")
    for model_name, urls in ALTERNATIVE_MODELS.items():
        dest = MODEL_DIR / model_name
        if dest.exists():
            print(f"{model_name} already exists, skipping")
            continue

        for url in urls:
            if download_file(url, dest):
                print(f"Successfully downloaded {model_name}")
                break
        else:
            print(f"Failed to download {model_name} from all sources")

    print("\nIf downloads failed, run with --placeholder to create dummy models for testing")
    print("Or manually place ONNX models in:", MODEL_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
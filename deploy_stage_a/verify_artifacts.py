import sys
import hashlib
import json
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_deployment_artifacts() -> bool:
    print("=" * 80)
    print("  STAGE A DEPLOYMENT ARTIFACT INTEGRITY CHECK")
    print("=" * 80)

    base_dir = Path(__file__).parent
    manifest_path = base_dir / "models" / "model_manifest.json"

    if not manifest_path.exists():
        print(f"❌ ERROR: Manifest file not found at {manifest_path}")
        return False

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    models_dir = manifest_path.parent
    scaler_file = models_dir / manifest["artifacts"]["scaler_filename"]
    model_file = models_dir / manifest["artifacts"]["model_filename"]

    if not scaler_file.exists():
        print(f"❌ ERROR: Scaler file not found at {scaler_file}")
        return False
    if not model_file.exists():
        print(f"❌ ERROR: Model file not found at {model_file}")
        return False

    scaler_hash = compute_sha256(scaler_file)
    model_hash = compute_sha256(model_file)

    expected_scaler_hash = manifest["artifacts"]["scaler_sha256"]
    expected_model_hash = manifest["artifacts"]["model_sha256"]
    expected_threshold = manifest["decision_rule"]["threshold_r"]

    print(f"  • Model File:       {model_file.name}")
    print(f"  • Model SHA256:     {model_hash}")
    print(f"  • Scaler File:      {scaler_file.name}")
    print(f"  • Scaler SHA256:    {scaler_hash}")
    print(f"  • Frozen Threshold: {expected_threshold:+.6f}R")

    if model_hash != expected_model_hash:
        print(f"❌ FATAL: Model SHA256 hash mismatch!")
        print(f"   Expected: {expected_model_hash}")
        print(f"   Actual:   {model_hash}")
        return False

    if scaler_hash != expected_scaler_hash:
        print(f"❌ FATAL: Scaler SHA256 hash mismatch!")
        print(f"   Expected: {expected_scaler_hash}")
        print(f"   Actual:   {scaler_hash}")
        return False

    if abs(expected_threshold - 0.3560245357269035) > 1e-9:
        print(f"❌ FATAL: Decision threshold modified! Expected 0.3560245357269035, got {expected_threshold}")
        return False

    print("\n✅ CERTIFICATION PASSED: All deployment artifacts match frozen research freeze 100%.")
    print("=" * 80 + "\n")
    return True


if __name__ == "__main__":
    if not verify_deployment_artifacts():
        sys.exit(1)
    sys.exit(0)

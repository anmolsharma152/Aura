# Aura — setup

Status: [STATUS.md](./STATUS.md). Full architecture: root README.

## Expected stack

- Linux (Wayland / GNOME target)  
- C toolchain + `libpam-dev` for PAM module  
- Python 3.11+ + ONNX Runtime for `aurad`  
- Camera `/dev/videoX`  

## Typical dev flow (high level)

```bash
cd ~/Projects/Aura
# follow README / docs for build order:
# 1) build aurad daemon and install unit
# 2) build pam_aura.so
# 3) enroll faces via config app
```

**Safety:** always keep a non-biometric login path while testing PAM modules.

Never commit private face embeddings or secrets.

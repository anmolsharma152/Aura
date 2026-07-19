# AGENTS.md

**Aura** — Linux edge facial authentication (PAM + daemon + ONNX).

- Resume: [docs/STATUS.md](./docs/STATUS.md)  
- Architecture in root README is authoritative  
- Never put heavy ML inside PAM process — keep client lean  
- Fail-safe bypass required while developing  
- No face biometric data in git  

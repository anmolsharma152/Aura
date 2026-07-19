# Aura — status handoff

| Field | Value |
|-------|--------|
| **As of** | 2026-07-19 |
| **Branch** | `develop` |
| **Product** | Edge facial auth for Linux — PAM client + `aurad` daemon + ONNX face/liveness |

Architecture source of truth: root [README.md](../README.md) + `docs/architecture-ideation.md`.

---

## Design status

| Component | Intent |
|-----------|--------|
| `pam_aura.so` | Lean C PAM client over Unix socket |
| `aurad` | Memory-resident Python daemon (ONNX MobileFaceNet + MiniFASNet) |
| Config GUI | GTK4 enrollment / settings |
| GNOME Shell extension | DBus feedback UI |

Implementation maturity: **architecture + ideation heavy**; treat code under `src/` / `run/` as evolving against the README spec.

---

## Next

- [ ] Align code tree with README component boundaries  
- [ ] Secure enrollment + TPM/keyring path as designed  
- [ ] Fail-open / fail-closed policy documented and tested  

---

## Resume

Read README § architecture, then [setup.md](./setup.md). Review notes: `docs/claude-architecture-review.txt`.

# IMAGE_RENDER Reference-Lock

Local-only production path for Curious Beyond. Paid APIs, cloud GPU and fallback without references are disabled.

Current gate: code components exist on the implementation branch but must not be called READY until tests and a real Windows/ComfyUI preflight pass. Reference conditioning requires local IPAdapter-compatible ComfyUI nodes/models. Rendering is serial for GTX 1650 4 GB.

First hardware acceptance target: one 1024x576 Scene 1 image, then QA/manifest, then the 21-scene batch.

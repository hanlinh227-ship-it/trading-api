"""Concrete runtime backends.

One backend at a time, proven end to end before the next is started. llama.cpp
is first because it is the only one that runs a real model on an ordinary CPU
with no accelerator, no service to stand up and no Python dependency tree.
"""

from .llama_cpp import LlamaCppBackend, LlamaCppBinary, detect_llama_cpp

__all__ = ["LlamaCppBackend", "LlamaCppBinary", "detect_llama_cpp"]

"""
Capability protocols for LLM providers.

Capabilities define what a provider can do (chat, embeddings, images, etc.).
Providers implement one or more capability protocols.
"""

from .chat import ChatCapability

__all__ = ["ChatCapability"]

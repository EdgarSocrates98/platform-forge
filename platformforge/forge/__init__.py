"""The Forge interoperability — capability manifest, delegation contracts,
A2A envelope, result receipts, evidence transfer."""

from platformforge.forge.delegate import Delegation, build_envelope, verify_envelope
from platformforge.forge.manifest import capability_manifest

__all__ = [
                                          "Delegation",
                                          "build_envelope",
                                          "capability_manifest",
                                          "verify_envelope",
]

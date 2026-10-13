"""The Forge interoperability — capability manifest, delegation contracts,
A2A envelope, result receipts, evidence transfer."""

from platformforge.forge.collect import collect_manifest, discover, ingest_facts
from platformforge.forge.delegate import Delegation, build_envelope, verify_envelope
from platformforge.forge.manifest import capability_manifest

__all__ = ["Delegation", "build_envelope", "capability_manifest",
           "collect_manifest", "discover", "ingest_facts", "verify_envelope"]

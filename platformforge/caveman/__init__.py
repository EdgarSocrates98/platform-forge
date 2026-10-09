"""Caveman — first-party output compression.

Reduce language, never substance. Protected spans (commands, paths, ids,
exceptions, warnings, IAM actions, ARNs, URLs, evidence, fact/rule ids,
numbers, units, versions) are never compressed away. Every compression emits
a receipt with before/after measurements.
"""

from platformforge.caveman.compress import CompressionReceipt, compress

__all__ = ["CompressionReceipt", "compress"]

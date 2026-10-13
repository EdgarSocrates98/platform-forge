"""Generic collection — sniff dump/artifact types and route to analyzers.

§7 `platformforge collect`: a bounded, offline ingress for artifacts a host
already produced (kubectl -o yaml dumps, terraform plan/state JSON, IAM
policy JSON, billing exports, SBOMs). Detection is by filename + shape;
undetected files are reported, never silently skipped.
"""

from platformforge.collect.detect import collect, detect_file

__all__ = ["collect", "detect_file"]

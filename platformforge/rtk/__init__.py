"""RTK — first-party command-output intelligence.

Tools dump thousands of lines; agents consume the compact form. Raw output is
preserved in the artifact store, expandable on demand.
"""

from platformforge.rtk.compact import CompactResult, compact_output, detect_command

__all__ = ["CompactResult", "compact_output", "detect_command"]

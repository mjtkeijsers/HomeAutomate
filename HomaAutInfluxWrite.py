"""Deprecated compatibility shim for the old typoed module name.

This module is kept only for backwards compatibility during the rename from
HomaAutInfluxWrite to HomeAutInfluxWrite.
"""

import warnings

warnings.warn(
    "HomaAutInfluxWrite is deprecated; import HomeAutInfluxWrite instead.",
    DeprecationWarning,
    stacklevel=2,
)

from HomeAutInfluxWrite import *  # noqa: F401,F403

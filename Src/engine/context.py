"""Shared mutable context threaded through every engine leaf."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .client import NodeClient


@dataclass
class EngineContext:
    """Carries all runtime state for a single engine run.

    Pass one instance to every leaf; never use module-level globals.
    """

    client: NodeClient
    evidence_dir: Path
    frames: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

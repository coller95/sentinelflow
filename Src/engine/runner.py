"""Tick runner: drives a py_trees behaviour tree to completion."""

from __future__ import annotations

import time
from datetime import datetime

import py_trees
import py_trees.behaviour
import py_trees.common
import py_trees.display
import py_trees.trees

Status = py_trees.common.Status


def run_tree(
    root: py_trees.behaviour.Behaviour,
    hz: float = 4.0,
    timeout_s: float = 90.0,
    verbose: bool = True,
) -> py_trees.common.Status:
    """Tick *root* at *hz* until SUCCESS, FAILURE, or wall-clock timeout.

    Returns the final root status (which may be RUNNING if timed out).
    """
    tree = py_trees.trees.BehaviourTree(root)
    period = 1.0 / hz
    deadline = time.monotonic() + timeout_s
    tick_count = 0

    while True:
        tick_start = time.monotonic()
        tree.tick()
        tick_count += 1

        if verbose:
            ts = datetime.now().isoformat(timespec="milliseconds")
            print(f"[{ts}] tick={tick_count}")
            print(py_trees.display.unicode_tree(root, show_status=True))

        current_status = root.status
        if current_status in (Status.SUCCESS, Status.FAILURE):
            return current_status

        if time.monotonic() >= deadline:
            if verbose:
                print(f"TIMEOUT after {timeout_s}s ({tick_count} ticks)")
            return root.status

        elapsed = time.monotonic() - tick_start
        sleep_for = max(0.0, period - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)

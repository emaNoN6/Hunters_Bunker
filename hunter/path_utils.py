#  ==========================================================
#  Hunter's Command Console
#  #
#  File: path_utils.py
#  Last Modified: 8/24/25, 2:02 PM
#  #
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================

# hunter/path_utils.py
# Utility functions to locate the project root and build paths relative to it.
# This avoids importing config_manager (which exits if config.ini is missing).

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

# Default markers that indicate the repository root when found in a directory
DEFAULT_MARKERS = (
    "config.ini",       # project-specific config at repo root
    "requirements.txt", # common Python project file
    ".git",             # VCS directory (optional in packaged distributions)
    "hunter",           # the main package directory
)


def _normalize_start_path(start_path: Optional[Path | str]) -> Path:
    """Normalize the start path to a directory Path.

    If start_path is None, use the current working directory.
    If start_path points to a file, use its parent directory.
    If it is already a directory, use it as-is.
    """
    if start_path is None:
        p = Path.cwd().resolve()
    else:
        p = Path(start_path).resolve()
    if p.is_file():
        return p.parent
    return p


@lru_cache(maxsize=8)
def find_project_root(start_path: Optional[Path | str] = None, markers: Optional[Iterable[str]] = None) -> Path:
    """Walk upward from start_path until a directory containing any marker is found.

    Args:
        start_path: File or directory to start the search from. If None, starts from CWD.
        markers: Filenames or directory names that indicate the project root.
                 If None, uses DEFAULT_MARKERS.
    Returns:
        Path to the discovered project root directory.
    Raises:
        FileNotFoundError: If no directory with the specified markers is found up to the filesystem root.
    """
    search_markers = tuple(markers) if markers is not None else DEFAULT_MARKERS
    current = _normalize_start_path(start_path)

    # Traverse up to the root
    while True:
        for m in search_markers:
            candidate = current / m
            if candidate.exists():
                return current
        # If we've reached the filesystem root, abort
        if current.parent == current:
            break
        current = current.parent

    raise FileNotFoundError(
        f"Could not locate project root starting from '{start_path or Path.cwd()}' looking for markers {search_markers}."
    )


def project_path(*parts: str | Path, start_path: Optional[Path | str] = None, markers: Optional[Iterable[str]] = None) -> Path:
    """Build a path relative to the discovered project root.

    Example:
        project_path('data', 'test_leads.json', start_path=__file__)
    """
    root = find_project_root(start_path=start_path, markers=markers)
    return root.joinpath(*map(str, parts))

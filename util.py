"""
Utility functions for Heliotorrent.

This module provides helper functions for working with tile paths,
creating torrents, and running external commands.
"""

import math
import logging
import os
from datetime import datetime
import sys
import subprocess
from typing import Generator, List, Optional, Tuple

from torf import Torrent
import humanize


TILE_SIZE = 256


def int_to_parts(tile_number: int) -> List[str]:
    """
    Convert an integer tile number to path parts.

    Args:
        tile_number: The tile number to convert

    Returns:
        A list of string parts representing the path components
    """
    # Pad the number to a multiple of 3 digits
    tile_str = str(tile_number).zfill(((len(str(tile_number)) + 2) // 3) * 3)
    # Split into groups of 3 digits
    parts = [f"{tile_str[j : j + 3]}" for j in range(0, len(tile_str), 3)]
    # Prefix all but the last part with 'x'
    parts = [f"x{x}" for x in parts[:-1]] + [parts[-1]]
    return parts


def paths_in_level(
    start_tile: int, end_tile: int, tree_size: int, partials: int = 0
) -> Generator[str, None, None]:
    """
    Generate paths for tiles in a specific level.

    Args:
        start_tile: First tile to include
        end_tile: Last tile to include (exclusive)
        tree_size: Total size of the tree
        partials: Number of partial entries (0 for none)

    Yields:
        Path strings for each tile
    """
    # Generate paths for complete tiles
    for i in range(start_tile, min(end_tile, tree_size)):
        parts = int_to_parts(i)
        yield "/".join(parts)

    # Generate path for partial tile if needed
    if partials:
        parts = int_to_parts(tree_size)
        parts[-1] += ".p"  # Mark as partial
        parts += [str(partials)]
        yield "/".join(parts)


def get_hash_tile_paths(
    start_entry: int,
    end_entry: int,
    tree_size: int,
    level_start: int = 0,
    level_end: int = 6,
    partials_req: bool = False,
) -> Generator[str, None, None]:
    """
    Generate paths for hash tiles.

    Args:
        start_entry: First entry to include
        end_entry: Last entry to include
        tree_size: Total size of the tree
        level_start: First level to include
        level_end: Last level to include (exclusive)
        partials_req: Whether to include partial tiles

    Yields:
        Path strings for each hash tile
    """
    for level in range(0, 6):
        start_entry //= TILE_SIZE
        end_entry = math.ceil(end_entry / TILE_SIZE)
        partials = (tree_size % TILE_SIZE) if partials_req else 0
        tree_size //= TILE_SIZE

        if level in range(level_start, level_end):
            yield from (
                f"tile/{level}/{x}"
                for x in paths_in_level(
                    start_entry, end_entry, tree_size, partials=partials
                )
            )


def get_data_tile_paths(
    start_entry: int, end_entry: int, tree_size: int, compressed: bool = False
) -> Generator[str, None, None]:
    """
    Generate paths for data tiles.

    Args:
        start_entry: First entry to include
        end_entry: Last entry to include
        tree_size: Total size of the tree
        compressed: Whether to use compressed data paths

    Yields:
        Path strings for each data tile
    """
    start_entry //= TILE_SIZE
    end_entry = math.ceil(end_entry / TILE_SIZE)
    tree_size //= TILE_SIZE

    prefix = "tile/compressed_data" if compressed else "tile/data"
    yield from (
        f"{prefix}/{x}" for x in paths_in_level(start_entry, end_entry, tree_size)
    )


def show_progress(torrent: Torrent, stage: str, current: int, total: int) -> None:
    """
    Display progress of torrent creation.

    Args:
        torrent: The torrent being created
        stage: Current stage of creation
        current: Current progress count
        total: Total items to process
    """
    percent = (current / total) * 100
    print(
        f"Building {torrent.name}: {stage} {percent:.2f}% ({current}/{total})",
        end="\r",
        flush=True,
    )


def create_torrent_file(
    name: str,
    author: str,
    paths: List[str],
    trackers: List[str],
    out_path: str,
    webseeds: Optional[List[str]] = None,
) -> Optional[Torrent]:
    """
    Create a torrent file from the given paths.

    Args:
        name: Name of the torrent
        author: Creator of the torrent
        paths: List of file paths to include
        trackers: List of tracker URLs
        out_path: Path to save the torrent file
        webseeds: List of webseed URLs

    Returns:
        The created Torrent object or None if creation failed
    """
    # Skip if torrent already exists
    if os.path.isfile(out_path):
        logging.debug(f"{out_path} already exists")
        return None

    # Check if all files exist
    missing_files = [p for p in paths if not os.path.exists(p)]
    if missing_files:
        for path in missing_files:
            logging.info(f"Missing file: {path}")
        logging.error(f"Missing files for torrent {name}")
        return None

    # Create and write torrent
    torrent = Torrent(
        trackers=trackers,
        private=False,
        created_by=author,
        creation_date=datetime.now(),
        webseeds=webseeds,
    )
    torrent.filepaths = paths
    torrent.name = name

    try:
        torrent.generate(threads=1)
        torrent.write(out_path, validate=False)
        logging.info(
            f"Wrote {out_path} with content size {humanize.naturalsize(torrent.size)}"
        )
        return torrent
    except Exception as e:
        logging.error(f"Failed to create torrent {name}: {e}")
        return None


def get_torrent_file_info(torrent_path: str) -> Optional[Tuple[str, int]]:
    """
    Extract info hash and length from a torrent file.

    Args:
        torrent_path: Path to the torrent file

    Returns:
        Tuple of (infohash, length) or None if extraction failed
    """
    t = Torrent.read(torrent_path, validate=False)
    return (t.infohash, t.size)


def run_scraper(paired_input: Tuple[List[str], List[str]]) -> None:
    """
    Run an external command with the given input.

    Args:
        paired_input: Tuple of (command, input_list)
    """
    command, input_list = paired_input
    logging.debug(
        f"Running command: {' '.join(command)}. First line of input: {input_list[0] if input_list else 'None'}"
    )

    try:
        result = subprocess.run(
            command,
            input="\n".join(input_list).encode(),
            stdout=sys.stdout,
            stderr=subprocess.PIPE,  # Capture stderr output
            check=True,
        )

        # Log any stderr output from successful command
        if result.stderr:
            logging.warning(f"Error running  {' '.join(command)}")
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            for line in stderr_text.splitlines():
                logging.warning(f"Command stderr: {line}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running {' '.join(command)}: {e.returncode}")
        # Log any stderr output from the failed command
        if e.stderr:
            stderr_text = e.stderr.decode("utf-8", errors="replace")
            for line in stderr_text.splitlines():
                logging.error(f"Command stderr: {line}")

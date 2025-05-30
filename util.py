import math
import logging
import hashlib
import os
from datetime import datetime
import sys
import subprocess

from torf import Torrent
import humanize
import bencodepy


TILE_SIZE = 256


def int_to_parts(i):
    tile_str = str(i).zfill(((len(str(i)) + 2) // 3) * 3)
    parts = [f"{tile_str[j:j+3]}" for j in range(0, len(tile_str), 3)]
    parts = [f"x{x}" for x in parts[:-1]] + [parts[-1]]
    return parts


def paths_in_level(start_tile, end_tile, tree_size, partials=0):
    for i in range(start_tile, min(end_tile, tree_size)):
        parts = int_to_parts(i)
        yield "/".join(parts)
    if partials:
        parts = int_to_parts(tree_size)
        parts[-1] += ".p"
        parts += [str(partials)]
        yield "/".join(parts)


def get_hash_tile_paths(
    start_entry, end_entry, tree_size, level_start=0, level_end=6, partials_req=False
):
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


def get_data_tile_paths(start_entry, end_entry, tree_size, compressed=False):
    start_entry //= TILE_SIZE
    end_entry = math.ceil(end_entry / TILE_SIZE)
    tree_size //= TILE_SIZE
    prefix = "tile/data" if not compressed else "tile/compressed_data"
    yield from (
        f"{prefix}/{x}" for x in paths_in_level(start_entry, end_entry, tree_size)
    )


def show_progress(torrent,stage, current, total):
    percent = (current / total) * 100
    print(f"Building {torrent.name}: {percent:.2f}% ({current}/{total})", end='\r', flush=True)
    sys.stdout.flush()

def create_torrent_file(name, author, paths, trackers, out_path):
    t = Torrent(
        trackers=trackers,
        private=False,
        created_by=author,
        creation_date=datetime.now(),
    )
    if os.path.isfile(out_path):
        logging.debug(f"{out_path} already exists")
        return
    if not all(os.path.exists(p) for p in paths):
        for p in paths:
            if not os.path.exists(p):
                logging.info(f"Missing file: {p}")
        logging.error(f"Missing files for torrent {name}")
        return
    t.filepaths = paths
    t.name = name
    t.generate(callback=show_progress,interval=0.1)
    print('\r',end='')
    t.write(out_path)
    logging.info(f"Wrote {out_path} with content size {humanize.naturalsize(t.size)}")


def get_torrent_file_info(tf):
    with open(tf, "rb") as f:
        meta = bencodepy.decode(f.read())

    info = meta[b"info"]
    info_encoded = bencodepy.encode(info)
    infohash = hashlib.sha1(info_encoded).hexdigest()

    length = 0
    if b"files" in info:  # multi-file
        length = sum(f[b"length"] for f in info[b"files"])
    else:  # single-file
        length = info[b"length"]
    return (infohash, length)

def run_scraper(paired_input):
    command, input_list = paired_input
    subprocess.run(
        command,
        input="\n".join(input_list).encode(),
        stdout=sys.stdout,
        check=True,
    )
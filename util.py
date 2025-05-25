import math
from urllib.parse import urlsplit
import urllib.request
import logging
import os
from glob import glob

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
        logging.debug(
            f"level={level} start={start_entry} end={end_entry}, tree_size={tree_size}"
        )
        start_entry //= TILE_SIZE
        end_entry = math.ceil(end_entry / TILE_SIZE)
        partials = (tree_size % TILE_SIZE) if partials_req else 0
        logging.debug(f"partials={partials}")
        tree_size //= TILE_SIZE
        if level in range(level_start,level_end):
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


def url_to_dir(url):
    return urlsplit(url).netloc


def get_checkpoint_location(outdir, monitoring_prefix):
    return f"{outdir}/{monitoring_prefix}/checkpoints/"


def save_checkpoint(outdir, monitoring_prefix, size, chkpt):
    d = get_checkpoint_location(outdir, monitoring_prefix)
    os.makedirs(d, exist_ok=True)
    fp = f"{d}/{size}"
    with open(fp, "w", encoding="utf-8") as w:
        w.write(chkpt)
    logging.debug(f"Wrote checkpoint of size {size} to {fp}")


def fetch_checkpoint(monitoring_prefix):
    with urllib.request.urlopen(f"{monitoring_prefix}/checkpoint") as r:
        chkpt = r.read().decode()
        size = chkpt.split("\n")[1]
        logging.debug(f"Fetched checkpoint of size {size} from {monitoring_prefix}")
        return int(size), chkpt


# TODO: Return path is inconsistent with other functions
def get_latest_checkpoint(outdir, monitoring_prefix):
    d = get_checkpoint_location(outdir, monitoring_prefix)
    latest = max((int(os.path.basename(x)) for x in glob(d + "*")))
    p = "checkpoints/" + str(latest)
    return (latest, p)

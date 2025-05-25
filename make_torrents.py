from datetime import datetime

import urllib
import os
import logging

from torf import Torrent
import humanize

from util import (
    get_data_tile_paths,
    get_hash_tile_paths,
    get_latest_checkpoint,
    url_to_dir,
)

TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)


def get_trackers(url):
    with urllib.request.urlopen(url) as r:
        return [x.decode().strip() for x in r.readlines() if len(x) > 1]


def paths_for_datatiles(start_index, stop_index, tree_size):
    paths = []
    paths += list(get_data_tile_paths(start_index, stop_index, tree_size))
    paths += list(
        get_hash_tile_paths(
            start_index, stop_index, tree_size, level_start=0, level_end=2
        )
    )
    return paths


def paths_for_top_tree(start_index, stop_index, tree_size):
    paths = []
    paths += list(
        get_hash_tile_paths(
            start_index,
            stop_index,
            tree_size,
            level_start=2,
            level_end=6,
            partials_req=True,
        )
    )
    return paths


def create_torrent(
    outdir,
    monitoring_path,
    start_index,
    stop_index,
    data_tiles,
    tree_size,
    trackers=None,
):
    t = Torrent(
        trackers=trackers,
        private=False,
        created_by="HelioTorrent v0.0.0",
        creation_date=datetime.now(),
    )
    paths = []
    if data_tiles:
        paths += paths_for_datatiles(start_index, stop_index, tree_size)
        level = "01"
    else:
        paths += paths_for_top_tree(start_index, stop_index, tree_size)
        _, p = get_latest_checkpoint(outdir, monitoring_path)
        paths += [p]
        level = "2345"

    if len(paths) == 0:
        logging.error(
            f"No tiles yet for {monitoring_path}-L{level}-{start_index}-{stop_index}"
        )
        return None

    paths = [f"data/{monitoring_path}/{x}" for x in paths]
    if not all(os.path.exists(p) for p in paths):
        for p in paths:
            if not os.path.exists(p):
                logging.info(f"Missing tile {p}")
        logging.error(
            f"Missing tiles for {monitoring_path}-L{level}-{start_index}-{stop_index}"
        )
        return None
    t.filepaths = paths

    # Comes last otherwise paths overwrites it.
    t.name = f"{monitoring_path}-L{level}-{start_index}-{stop_index}"
    return t


def get_torrent_path(outdir, monitoring_path, data_tiles, start_index, stop_index):
    if data_tiles:
        level = "01"
    else:
        level = "2345"
    return f"{outdir}/{monitoring_path}/torrents/L{level}-{start_index}-{stop_index}.torrent"


def build_torrents(outdir, monitoring_prefix, size):
    # Data Tiles
    for i in range(4096 * 256, size, 4096 * 256):
        start = i - (4096 * 256)
        end = i

        op = get_torrent_path(outdir, monitoring_prefix, True, start, end)

        if os.path.isfile(op):
            logging.info(f"{op} already exists")
            continue

        os.makedirs(os.path.dirname(op), exist_ok=True)

        t = create_torrent(
            outdir, monitoring_prefix, start, end, True, size, trackers=good_trackers
        )
        if not t:
            logging.error(f"Error generating torrent file {op}")
            continue
        t.generate()
        t.write(op)

        logging.info(f"Wrote {op} with content size {humanize.naturalsize(t.size)}")

    # Top Tiles
    op = get_torrent_path("data", monitoring_prefix, False, 0, size)
    if os.path.isfile(op):
        logging.info(f"{op} already exists")
        return
    t = create_torrent(
        "data", monitoring_prefix, 0, size, False, size, trackers=good_trackers
    )
    if t:
        t.generate()
        t.write(op)
        logging.info(f"Wrote {op} with content size {humanize.naturalsize(t.size)}")


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

good_trackers = get_trackers(TRACKER_LIST_URL)
logging.info(f"Discovered {len(good_trackers)} trackers from {TRACKER_LIST_URL}")

LOG_URL = "https://tuscolo2026h1.skylight.geomys.org/"
log_dir = url_to_dir(LOG_URL)
latest_size, _ = get_latest_checkpoint("data", log_dir)

build_torrents("data", log_dir, latest_size)

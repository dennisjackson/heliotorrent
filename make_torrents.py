from torf import Torrent
from util import *
from datetime import datetime
import humanize
import urllib
import os
import logging

TRACKER_LIST_URL = (
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
)

def get_trackers(url):
    with urllib.request.urlopen(url) as r:
        return [x.decode().strip() for x in r.readlines() if len(x) > 1]

def create_torrent(monitoring_path, startIndex, stopIndex, data_tiles, treeSize,trackers=None):
    t = Torrent(
        trackers=trackers,
        private=False,
        created_by="HelioTorrent v0.0.1",
        creation_date=datetime.now(),
    )
    paths = []
    if data_tiles:
        paths += [x for x in get_data_tile_paths(startIndex, stopIndex, treeSize)]
        paths += [x for x in get_hash_tile_paths(startIndex, stopIndex, treeSize,levelStart=0,levelEnd=2)]
        level='01'
    else:
        paths += [x for x in get_hash_tile_paths(startIndex, stopIndex, treeSize,levelStart=2,levelEnd=6)]
        level = '2345'

    paths = [f"data/{monitoring_path}/{x}" for x in paths]
    if len(paths) == 0:
        logging.error(f"No tiles yet for {monitoring_path}-L{level}-{startIndex}-{stopIndex}")
        return None
    if not all(os.path.exists(p) for p in paths):
        logging.error(f"Missing tiles for {monitoring_path}-L{level}-{startIndex}-{stopIndex}")
        return None
    t.filepaths = paths

    # Comes last otherwise paths overwrites it.
    t.name = f"{monitoring_path}-L{level}-{startIndex}-{stopIndex}"
    return t

def get_torrent_path(outdir,monitoring_path,level,startIndex,stopIndex):
    return f"{outdir}/{monitoring_path}/torrents/L{level}-{startIndex}-{stopIndex}.torrent"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

trackers = get_trackers(TRACKER_LIST_URL)
logging.info(f"Discovered {len(trackers)} trackers from {TRACKER_LIST_URL}")

LOG_URL = "https://tuscolo2026h1.skylight.geomys.org/"
p = url_to_dir(LOG_URL)
size, _ = get_checkpoint(LOG_URL)

for data_tiles in [True,False]:
    for i in range(4096*256,size,4096*256):
        start = i - (4096*256)
        end = i

        op = get_torrent_path('data',p,level,start, end)

        if os.path.isfile(op):
            logging.info(f"{op} already exists")
            continue

        os.makedirs(os.path.dirname(op), exist_ok=True)

        t = create_torrent(p, start, end, data_tiles, size,trackers=trackers)
        if not t:
            logging.error(f"Error generating torrent file {op}")
            continue
        t.generate()
        t.write(op)

        logging.info(f"Wrote {op} with content size {humanize.naturalsize(t.size)}")
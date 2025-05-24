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

def create_torrent(monitoring_path, startIndex, stopIndex, treeSize,trackers=None):
    t = Torrent(
        trackers=trackers,
        private=False,
        created_by="HelioTorrent v0.0.1",
        creation_date=datetime.now(),
    )

    paths = [x for x in get_data_tile_paths(startIndex, stopIndex, treeSize)]
    paths += [x for x in get_hash_tile_paths(startIndex, stopIndex, treeSize)]
    paths = [f"data/{monitoring_path}/{x}" for x in paths]
    t.filepaths = paths

    # Comes last otherwise paths overwrites it.
    t.name = f"{monitoring_path}-{startIndex}-{stopIndex}"
    return t

def get_torrent_path(outdir,monitoring_path,startIndex,stopIndex):
    return f"{outdir}/{monitoring_path}/torrents/{startIndex}-{stopIndex}.torrent"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

p = url_to_dir("https://tuscolo2026h1.skylight.geomys.org/")

op = get_torrent_path('data',p,0, 4096 * 256)
if os.path.isfile(op):
    logging.info(f"{op} already exists")
    exit(0)
os.makedirs(os.path.dirname(op), exist_ok=True)

trackers = get_trackers(TRACKER_LIST_URL)
logging.info(f"Discovered {len(trackers)} trackers from {TRACKER_LIST_URL}")

t = create_torrent(p, 0, 4096 * 256, 10879387,trackers=trackers)
t.generate()
t.write(op)

logging.info(f"Wrote {op} with content size {humanize.naturalsize(t.size)}")

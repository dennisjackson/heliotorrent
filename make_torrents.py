from torf import Torrent
from util import *
from datetime import datetime
import humanize
import urllib
import os

# Strategy
# Easy to block by 4096 tiles per bundle on the lower layer.
# Then we get 16 higher level tiles.

# The higher levels are going to be pretty small?
# 1 / 256^2 of the

TRACKER_URL = "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"

def get_trackers(url):
    with urllib.request.urlopen(url) as r:
        return [x.decode().strip() for x in r.readlines() if len(x) > 1]

GOOD_TRACKERS = get_trackers(TRACKER_URL)

def make_torrent(monitoring_path, startIndex, stopIndex, treeSize):
    paths = [x for x in get_data_tile_paths(startIndex, stopIndex, treeSize)]
    paths += [x for x in get_hash_tile_paths(startIndex, stopIndex, treeSize)]
    paths += []  # Checkpoints TODO
    paths += []  # Issuers TODO
    # webseeds and httpseeds don't seem to work natively because of prefixing behavior.
    file_prefix = f'data/{monitoring_path}'
    paths = [f'{file_prefix}/{x}' for x in paths]
    # print(paths)
    t = Torrent(
        trackers=GOOD_TRACKERS,
        private=False,
        comment="TODO",
        created_by='HelioTorrent',
        creation_date=datetime.now(),
    )
    t.filepaths = paths
    # Comes last otherwise paths overwrites it.
    t.name = f"{monitoring_path}-{startIndex}-{stopIndex}"
    return t

p = url_to_dir('https://tuscolo2026h1.skylight.geomys.org/')
t = make_torrent(p,0,4096*256,10879387)

t.generate()
os.makedirs('data/torrents', exist_ok=True)
t.write(f'data/torrents/{t.name}.torrent')

# TODO - Need to skip if the file already exists.

# TODO - Compression with zstd might offer around a 50% bandwidth saving. (Applied to data tiles)

print(humanize.naturalsize(t.size))
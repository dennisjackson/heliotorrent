from torf import Torrent
from util import *

# Strategy
# Easy to block by 4096 tiles per bundle on the lower layer.
# Then we get 16 higher level tiles.

# The higher levels are going to be pretty small?
# 1 / 256^2 of the


def make_torrent(monitoring_path, startIndex, stopIndex, treeSize):
    paths = [x for x in get_data_tile_paths(startIndex, stopIndex, treeSize)]
    paths += [x for x in get_hash_tile_paths(startIndex, stopIndex, treeSize)]
    paths += []  # Checkpoints
    paths += []  # Issuers
    # webseeds and httpseeds don't seem to work natively because of prefixing behavior.
    Torrent(
        name="TODO",
        trackers=[],
        private=False,
        comment="TODO",
        path="TODO",
        exclude_globs="*",
        include_globs="TODO",
    )

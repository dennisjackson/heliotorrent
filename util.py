import math
from urllib.parse import urlsplit

TILE_SIZE = 256


def paths_in_level(start_tile, end_tile, treeSize):
    for i in range(start_tile, min(end_tile, treeSize)):
        tile_str = str(i).zfill(((len(str(i)) + 2) // 3) * 3)
        parts = [f"{tile_str[j:j+3]}" for j in range(0, len(tile_str), 3)]
        parts = [f"/x{x}" for x in parts[:-1]] + [parts[-1]]
        yield "/".join(parts)


def get_hash_tile_paths(startEntry, endEntry, treeSize):
    for level in range(0, 6):
        startEntry //= TILE_SIZE
        endEntry = math.ceil(endEntry / TILE_SIZE)
        treeSize //= TILE_SIZE
        yield from (
            f"tile/{level}/{x}" for x in paths_in_level(startEntry, endEntry, treeSize)
        )


def get_data_tile_paths(startEntry, endEntry, treeSize,compressed=False):
    startEntry //= TILE_SIZE
    endEntry = math.ceil(endEntry / TILE_SIZE)
    treeSize //= TILE_SIZE
    prefix = "tile/data" if not compressed else "tile/compressed_data"
    yield from (
        f"{prefix}/{x}" for x in paths_in_level(startEntry, endEntry, treeSize)
    )

def url_to_dir(url):
    return urlsplit(url).netloc
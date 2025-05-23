

# Tiles are served as at
#     <monitoring prefix>/tile/<L>/<N>[.p/<W>]
# with `Content-Type: application/octet-stream`.
# `<L>` is the “level” of the tile, and MUST be a decimal ASCII integer between 0
# and 5, with no additional leading zeroes.
# `<N>` is the index of the tile within the level. It MUST be a non-negative
# integer encoded into 3-digit path elements. All but the last path element MUST
# begin with an `x`. For example, index 1234067 will be encoded as
# `x001/x234/067`.

import math
import subprocess
import sys

TILE_SIZE = 256
USER_AGENT = 'Experimental CT scraper using wget. Contact: scraper-reports@dennis-jackson.uk'

def paths_in_level(start_tile,end_tile,treeSize):
    for i in range(start_tile,min(end_tile,treeSize)):
        tile_str = str(i).zfill(((len(str(i)) + 2) // 3) * 3)
        parts = [f'{tile_str[j:j+3]}' for j in range(0, len(tile_str), 3)]
        parts = [f'/x{x}' for x in parts[:-1]] + [parts[-1]]
        yield '/'.join(parts)

def get_hash_tile_paths(startEntry, endEntry,treeSize):
    for level in range(0,6):
        startEntry //= TILE_SIZE
        endEntry = math.ceil(endEntry / TILE_SIZE)
        treeSize //= TILE_SIZE
        yield from (f"tile/{level}/{x}" for x in paths_in_level(startEntry,endEntry,treeSize))

def get_data_tile_paths(startEntry,endEntry,treeSize):
    startEntry //= TILE_SIZE
    endEntry = math.ceil(endEntry / TILE_SIZE)
    treeSize //= TILE_SIZE
    yield from (f"tile/data/{x}" for x in paths_in_level(startEntry,endEntry,treeSize))

def run_wget(output_dir,monitoring_path,tiles):
    command = [
        'wget',
        '--input-file=-',
        f'--base={monitoring_path}',
        '--no-clobber',
        '--retry-connrefused',
        '--retry-on-host-error',
        f'--directory-prefix={output_dir}',
        '--compression=gzip',
        '--no-verbose',
        '--force-directories'
    ]
    subprocess.run(command, input="\n".join(tiles).encode(), stdout=sys.stdout)

# print([x for x in get_data_tile_paths(0,1024,2048)])
# print([x for x in get_data_tile_paths(0,1004*256,9999*256)])
run_wget('data','https://tuscolo2026h1.skylight.geomys.org/',[x for x in get_data_tile_paths(0,10879387,10879387)])
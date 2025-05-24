# Tiles are served as at
#     <monitoring prefix>/tile/<L>/<N>[.p/<W>]
# with `Content-Type: application/octet-stream`.
# `<L>` is the “level” of the tile, and MUST be a decimal ASCII integer between 0
# and 5, with no additional leading zeroes.
# `<N>` is the index of the tile within the level. It MUST be a non-negative
# integer encoded into 3-digit path elements. All but the last path element MUST
# begin with an `x`. For example, index 1234067 will be encoded as
# `x001/x234/067`.


import subprocess
import sys
from util import *


USER_AGENT = (
    "Experimental CT scraper using wget. Contact: scraper-reports@dennis-jackson.uk"
)


def run_wget(output_dir, monitoring_path, tiles):
    command = [
        "wget",
        "--input-file=-",
        f"--base={monitoring_path}",
        "--no-clobber",
        "--retry-connrefused",
        "--retry-on-host-error",
        f"--directory-prefix={output_dir}",
        "--compression=gzip",
        "--no-verbose",
        "--force-directories",
    ]
    subprocess.run(command, input="\n".join(tiles).encode(), stdout=sys.stdout)


# print([x for x in get_data_tile_paths(0,1024,2048)])
print([x for x in get_hash_tile_paths(0, 257, 9999 * 256 * 256)])
# run_wget('data','https://tuscolo2026h1.skylight.geomys.org/',[x for x in get_data_tile_paths(0,10879387,10879387)])
# run_wget('data','https://tuscolo2026h1.skylight.geomys.org/',[x for x in get_hash_tile_paths(0,256*1024,10879387)])

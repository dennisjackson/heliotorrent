from util import *
import subprocess
import os


def compress_tile(input_path, output_path):
    command = [
        "tar",
        "--zstd",
        "-cf",
        output_path,
        input_path,
    ]
    subprocess.run(command, check=True)


log_path = url_to_dir("https://tuscolo2026h1.skylight.geomys.org")
compress_dir = f"data/{log_path}/tile/compressed_data"
os.makedirs(compress_dir, exist_ok=True)

for x in get_data_tile_paths(0, 256 * 4096, 10879387, compressed=False):
    cp = x.replace("tile/data/", "tile/compressed_data/")
    # print(f'{x} -> {cp}')
    os.makedirs("/".join(f"data/{log_path}/{cp}".split("/")[:-1]), exist_ok=True)
    compress_tile(f"data/{log_path}/{x}", f"data/{log_path}/{cp}")

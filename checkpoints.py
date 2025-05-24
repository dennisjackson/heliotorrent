import os
import time
import datetime
from util import *

log = "https://tuscolo2026h1.skylight.geomys.org/"
log_dir = url_to_dir(log)
path = f"data/{log_dir.strip()}/checkpoints"
os.makedirs(path, exist_ok=True)

while True:
    size, chkpt = get_checkpoint(log)
    fp = f"{path}/{size}"
    with open(fp, "w") as w:
        w.write(chkpt)
        print(f"{datetime.datetime.now()} - Wrote checkpoint of size {size} to {fp}")
    time.sleep(300)

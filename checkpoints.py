import os
import time
import datetime
from util import *

log = "https://tuscolo2026h1.skylight.geomys.org/"
log_dir = url_to_dir(log)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

while True:
    size, chkpt = fetch_checkpoint(log)
    save_checkpoint("data", log_dir, size, chkpt)
    logging.info(f"Wrote checkpoint of size {size} to {fp}")
    time.sleep(300)

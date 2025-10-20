#  Setting up a HelioTorrent instance

This document describes how to use the software in this repository to serve Static CT over BitTorrent. Running HelioTorrent doesn't require any privileged access to a Static CT log, it uses the public monitoring interface.

Providers interested in using their own software stack should see [Spec](spec.md) and [Design](design.md).

## Overview

HelioTorrent is made up of a Python component by the same name which produces torrents, effectively working as a static site generator and a Rust component called Heliostat which seeds those torrents over HTTP(S). The two components are closely integrated, sharing a config file and orchestration script. This document walks through setting them up.

## Setting up HelioTorrent

HelioTorrent is a Python application managed with [uv](https://docs.astral.sh/uv/). It needs network access, roughly 2 GB of scratch space per log, and writes generated torrent files and feeds to a specified folder. That folder can then be served over HTTP by Heliostat, or by your preferred hosting platform.

1. Fetch a copy of the source with `git clone https://github.com/dennisjackson/heliotorrent.git`.
2. Install the dependencies with `uv sync`. If you don't have `uv`, see the instructions [here](https://docs.astral.sh/uv/getting-started/installation/).
3. Install `wget2` via your package manager of choice.
4. Generate a configuration file interactively: `uv run heliotorrent.py --generate-config --interactive`.

The configuration file is YAML-formatted. An example listing is given below, but HelioTorrent will walk you through the various options interactively:

```yaml
# Global settings for HelioTorrent
# Configure directories, ports, and the base feed URL. Each log's feed defaults to <feed_url_base>/<log_name>/feed.xml.
data_dir: data
torrent_dir: torrents
# https_port: 8443
http_port: 8080
# tls_cert: null
# tls_key: null
feed_url_base: http://127.0.0.1:8080/torrents
scraper_contact_email: null # Required; this must be set
frequency: 3600
entry_limit: 0
delete_tiles: true
webseeds:
- http://127.0.0.1:8080/webseed/
logs:
- name: tuscolo2026h1
  log_url: https://tuscolo2026h1.skylight.geomys.org/
# You can add more logs here. Optional keys override the global defaults above.
#  - name: "another-log"
#    log_url: "https://another.log.server/log/"
    # Optional Keys:
    # feed_url: "http://127.0.0.1/alternative-location/feed.xml"
    # frequency: 300
    # entry_limit: null
    # delete_tiles: false
    # webseeds:
    #  - "http://webseed.example.com/"
```

If you want, you can run HelioTorrent independently with :
```
uv run heliotorrent.py --config <your_config_file>
```

But you probably want to setup Heliostat as well.

## Setting up Heliostat

Heliostat is a Rust application located in the `heliostat/` directory. To build it, run `cargo build --release` in `heliostat/`. It shares the same configuration file format as HelioTorrent.

HTTPS support is nice to have, if not essential, and can be configured via `certbot`. You'll need to make the resulting TLS certificate and private key readable to Heliostat and then configure the paths and the HTTPS port in the config file.

Although you can run Heliostat independently, HelioTorrent can also start it for you. Add `--heliostat <path-to-binary>` to the HelioTorrent invocation. For example:

```
uv run heliotorrent.py --config <your_config_file> --heliostat heliostat/target/release/heliostat
```

## Running as a Daemon

By default HelioTorrent logs messages to the `logs` directory and to the console. You can configure HelioTorrent as a service with systemd, or run it in the background under a session manager such as `tmux` or `screen`.

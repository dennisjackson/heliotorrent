# HelioTorrent Design

HelioTorrent consists of two components that work together to publish and serve Static CT data over BitTorrent:

- HelioTorrent (Python) — packages [Static CT API](static-ct-api.md) logs into .torrent files and machine-readable feeds (RSS/JSON). It’s a small static‑site generator for Tile Torrents.
- Heliostat (Rust) — a WebSeed server for those torrents, acting as a proxy that serves the Static CT files to BitTorrent clients via the WebSeed mechanism defined by [BEP 19](https://www.bittorrent.org/beps/bep_0019.html).

They can run together and share a single YAML configuration format, but either could be operated independently.

## HelioTorrent

### Inputs and outputs

HelioTorrent takes a YAML configuration file (see [providers.md]) and writes output to a target directory with this structure:

```
index.html
<log-name>/
  *.torrent
  feed.xml
  index.html
  torrents.json
```

This directory is intended to be offered via HTTP(S).

### Workflow

For each configured log, HelioTorrent starts a separate background process which repeatedly:

- Fetches the latest checkpoint from the log.
- Inspects the output directory to determine what torrents already exist.
- If new data is available:
  - Downloads the relevant tiles with `wget2`.
  - Generates a .torrent file with `torf`.
  - Regenerates the RSS and JSON feeds for the log.
  - Regenerates the HTML status pages.
- Sleeps for a configured interval, then repeats.

### Structure

- `lib/`
  - `interactive_config.py` — interactive generation of HelioTorrent configuration files
  - `tilelog_html.py` — HTML status page generation
  - `TileLog.py` — library core
  - `util.py` — wrappers for external tools (e.g., `wget2`, `torf`)
- `tests/` — pytest-based tests (run with `uv run pytest`; requires network access)
- `static/` — static assets used in generated HTML
- `heliotorrent.py` - CLI, driver and main loop.

## Heliostat

### Inputs and outputs

Heliostat is a Rust HTTP server. It uses the same YAML configuration format as HelioTorrent (see [providers.md]).

For each configured log, Heliostat exposes a WebSeed endpoint at `/webseed/<log_name>`. Requests to

```
/webseed/<log_name>/<torrent_name>/<file_path>
```

are mapped to the corresponding Static CT Monitoring URL:

```
<log_url>/<file_path>
```

- Because many BitTorrent clients don’t accept compressed responses, Heliostat serves uncompressed bodies.
- Because clients often use range requests, Heliostat fetches whole files from the upstream log and stores them in an in‑memory LRU cache to avoid repeated log requests.

Heliostat also serves the generated torrent files and other static files under `/torrents/`, and exposes a non-advertised `/statistics` endpoint reporting per‑log request counts, bandwidth, and cache hit rate.

### Workflow

Heliostat uses [axum](https://docs.rs/axum) (built on [Tokio](https://tokio.rss)) to define HTTP routes and handlers.
It uses [reqwest](https://docs.rs/reqwest) with connection pooling to fetch from the upstream log, and caches responses in a per‑log in‑memory cache.

One special case is the top‑level `README.md` file included in each torrent. It does not exist on the log server, so Heliostat serves it from the local torrent directory.

## Development practices

- Testing
  - HelioTorrent: `uv run pytest`
  - Heliostat: `cargo test`
- Linting/formatting
  - HelioTorrent: `uv run ruff check`
  - Heliostat: `cargo clippy`, `cargo fmt`
- Subtree management
  - Heliostat is vendored as a git subtree. Update with:

```
git subtree pull --prefix=heliostat git@github.com:dennisjackson/heliostat.git master --squash
```

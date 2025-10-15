# Heliotorrent

Heliotorrent turns Static Certificate Transparency logs into torrents.

## Requirements

- Python
- [`wget2`](https://gitlab.com/gnuwget/wget2) available on `PATH` (
- [`uv`](https://docs.astral.sh/uv/) is recommended

## Install

```bash
uv sync --locked
```

## Configure

Heliotorrent reads a single YAML configuration file. You can start from the built-in template:

```bash
uv run python heliotorrent.py --generate-config > config.yaml
```

Or derive one from the Chrome CT log list:

```bash
uv run python heliotorrent.py --generate-config-from-log-list > config.yaml
```

Key settings:

| Key | Description |
| --- | --- |
| `data_dir` | Root directory that stores tiles and checkpoints (`<data_dir>/<log_name>/tile/...`). |
| `torrent_dir` | Destination for generated torrents and feeds (`<torrent_dir>/<log_name>/`). |
| `feed_url_base` | Base URL advertised inside RSS feeds. Defaults to `http://127.0.0.1/torrents`. |
| `frequency` | Seconds between polling runs. Set to `0` for a single pass. |
| `entry_limit` | Optional maximum tree size to process. |
| `delete_tiles` | Remove tiles after creating torrents to save disk space. |
| `webseeds` | Global list of webseed URLs; can be overridden per log. |

Each item under `logs` must include at least:

```yaml
logs:
  - name: tuscolo2026h1
    log_url: https://tuscolo2026h1.skylight.geomys.org/
    # Optional per-log overrides:
    # feed_url: http://example.com/torrents/tuscolo2026h1/feed.xml
    # frequency: 600
    # entry_limit: 1048576
    # delete_tiles: false
    # webseeds: []
```

Fields you omit inherit the global defaults. When `feed_url` is not provided, Heliotorrent combines `feed_url_base` and the log `name`.

## Run

```bash
uv run python heliotorrent.py --config config.yaml
```

Use `--verbose` for debug-level logging. The process will stagger workers with a random initial delay.

Outputs:

- `data/<log_name>/tile/…` – downloaded data and hash tiles
- `data/<log_name>/checkpoint/` – fetched checkpoints
- `torrents/<log_name>/L01-*-*.torrent` – per-leaf torrents
- `torrents/<log_name>/L2345-0-<size>.torrent` – upper tree torrent, refreshed when needed
- `torrents/<log_name>/feed.xml` – RSS 2.0 feed with enclosure entries for each torrent

Stop the service gracefully to allow workers to finish writing torrents. If you only need to prepare torrents once (e.g. in CI), set `frequency: 0` globally and per-log.

## Testing & Development

- `uv run pytest` runs the unit tests.
- `uv run python heliotorrent.py --config test_config.yaml --verbose` performs a local smoke test against public logs (ensure you are comfortable with the bandwidth requirements first).

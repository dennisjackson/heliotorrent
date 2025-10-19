# Heliotorrent

![experiments/logo.png]

Heliotorrent turns Static Certificate Transparency logs into torrents and seeds them.

There's a [running instance](https://heliostat.dennis-jackson.uk:8443) you can browse. There's also a [draft specification](docs/spec.md) and a [design doc](docs/design.md).

## Consuming Tiles from HelioTorrent

HelioTorrent is compatible with most existing BitTorrent clients. See the instructions in [docs/clients.md].


## Running HelioTorrent as Provider

See the detailed instructions in [docs/providers.md].

### Requirements

- Python with [`uv`](https://docs.astral.sh/uv/) is recommended
- [`wget2`](https://gitlab.com/gnuwget/wget2) available on `PATH` (
- Rust / Cargo.

### Install

Install the Python dependencies:

```bash
uv sync --locked
```

Compile the Heliostat Rust Crate:

```bash
cd heliostat
cargo build --release
```

### Configure

Heliotorrent reads a single YAML configuration file. You can start from the built-in template:

```bash
uv run python heliotorrent.py --generate-config --interactive
```

### Run

```bash
uv run python heliotorrent.py --config config.yaml
```
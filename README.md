# HelioTorrent

<img src="docs/logo.png" alt="Project logo of a sun rising over a waterfall" width="300" height="300">

HelioTorrent packages Static Certificate Transparency (CT) tiles into .torrent files, publishes them to RSS and JSON feeds and seeds them over HTTP(S).

- Live demo: https://heliostat.dennis-jackson.uk:8443
- Spec: [docs/spec.md](docs/spec.md)
- Design: [docs/design.md](docs/design.md)

## Consume Tiles (Clients)

HelioTorrent works with any BitTorrent client that supports RSS (most of them). See [docs/clients.md](docs/clients.md) for step‑by‑step guides (Transmission, qBittorrent, etc.). The quick version is below.

1. Install [Transmission](https://transmissionbt.com/) and enable local API access.
2. Install Flexget with [uv](https://github.com/astral-sh/uv): `uv tool install flexget[transmission]`
3. Grab the example config in [docs/flexget.yaml](docs/flexget.yaml)
4. Run Flexget: `flexget -c flexget.yaml execute` 

## Run HelioTorrent (Server)

Full instructions are in [docs/providers.md](docs/providers.md). The quick version is below.

### Requirements

- Python (managed with `uv` is recommended)
- `wget2` available on `PATH`
- Rust/Cargo

### Install

Install Python dependencies:

```bash
uv sync --locked
```

Build the Heliostat Rust crate:

```bash
cd heliostat
cargo build --release
```

### Configure

HelioTorrent uses a single YAML config file. Generate one interactively:

```bash
uv run heliotorrent.py --generate-config --interactive
```

### Run

Run HelioTorrent using your config file:

```bash
uv run heliotorrent.py --config config.yaml --heliostat heliostat/target/release/heliostat
```

## Documentation

- Consuming tiles: [docs/clients.md](docs/clients.md)
- Operating a provider: [docs/providers.md](docs/providers.md)
- Specification: [docs/spec.md](docs/spec.md)
- Design notes: [docs/design.md](docs/design.md)

## License

[Mozilla Public License](LICENSE).

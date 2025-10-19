# HelioTorrent

![HelioTorrent logo](docs/logo.png)

HelioTorrent packages Static Certificate Transparency (CT) tiles into .torrent files, publishes them via feeds and seeds them over HTTP(S).

- Live demo: https://heliostat.dennis-jackson.uk:8443
- Spec: [docs/spec.md](docs/spec.md)
- Design: [docs/design.md](docs/design.md)

## Consume Tiles

HelioTorrent works with most BitTorrent clients that support RSS. See [docs/clients.md](docs/clients.md) for step‑by‑step guides (Transmission + FlexGet, qBittorrent, etc.).

## Run HelioTorrent yourself

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

Mozilla Public License - See [LICENSE](LICENSE).

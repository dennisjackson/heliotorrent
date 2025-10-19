# Setting up a HelioTorrent instance

HelioTorrent can be configured by anybody. This document describes how to use the software in this repository to serve Static CT over BitTorrent. Providers interested in using their own software stack should see [Spec.md] and [Design.md].

Running HelioTorrent doesn't require any privileged access to a static CT log.

## Setting up HelioTorrent

HelioTorrent is a python application packaged with [uv]. HelioTorrent needs network access, roughly 2 GB of scratch space per log, and outputs generated torrent files and feeds to a specified folder. This folder can then be served over HTTP with Heliostat, or your preferred hosting platform of choice.

1. Fetch a copy of the source with `git clone <TODO>`.
2. Install the dependencies with `uv ...`. If you don't have a copy of `uv`, see the instructions here.
3. Install wget2
4. You can generate a configuration file interactively with the command `uv run heliotorrent.py --TODO`.

The configuration file is YAML-formatted. A listing is given below:

TODO.

5. You can now run HelioTorrent with `uv run heliotorrent.py --TODO`.

By default HelioTorrent will log messages to the `log` directory and to the console. You can configure HelioTorrent as a service with systemD:

TODO.

Or simply leaving it running in the background with `termux`:

## Setting up Heliostat

Heliostat is a rust application packaged in the heliostat directory. If you'd like to build it, you need to invoke `cargo build --release`. It shares the same configuration file format as HelioTorrent and it's interactive configuration file generator will guide you through setup.

The key options are:

TODO.

HTTPS support is nice to have, if not essential, and can be configured via `certbot`.

You don't need to run Heliostat independly, simply extend the heliotorrent invoation with `--heliostat <path-to-binary>. By default, that would look like:

`uv run ... --heliostat ...`

Heliostat could be run independently of HelioTorrent, however, it does need to serve the README.md files to clients.

## Multiple Instances

HelioTorrent is designed so that the torrents it produces are instance-independent, meaning that independent instances publishing torrents should result in the same torrent metahashes, meaning that their peers will join the same swarm and be able to exchange bandwidth.

Hosting a webseed contributes bandwidth to a swarm. However, peers can only discover webseeds through torrent files - they can't be learned through peer exchange - meaning that
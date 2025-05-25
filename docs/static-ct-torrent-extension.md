# Static CT Torrent Extension Spec

* TOOD: C2SP Conventions

## Torrent Creation

* Torrents are partitioned into two types

### Data Leaves

* Data Leaves are: 4096 Data Tiles, 4096 L0 Hash Tiles, 16 L1 Hash Tiles
* They are named...
* They never contain partials
* Non-overlapping and non-redundant
* Expected size of this torrent.
* Avoid too many torrents.

### Tree Heads

* Tree Heads contain tiles L2-L5 and a checkpoint
* Checkpoint is named.
* I guess issuers ought to go in here as well?
* Overlapping. Smart clients will not need to redownload however.
* Max Size of this torrent.

## Serving Torrents

* Two different entities can both generate the same torrents
* Data Leaves will be shared. Tree Heads will not unless for same id.

### Torrent Files

* Served at
* named
* Should be hybrids

### feed.xml

* Served at
* Entry contents
* Two channels?

###  HTTP Sources

* If server supports it.
* Setup a redirect.
* Encode into torrent files.

## Client Behavior

### Storage

* Store without subdirectories
* Setup RSS subscription

### Validation

* Just like a normal log!

### Transparent Mode

* Local webserver.
* Alias for checkpoints locally.
* Depending on where issuers lands.. proxy that as well.
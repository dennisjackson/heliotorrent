
## Static CT Scraper

* Don't want to hold them all in memory.
* Don't want to parse them. Alternative way to get all the issuers? Feel like the parsing might be wrong and might be missing the length prefix of each data entry?
* Does it handle existing entries correctly?

## Torrent Generator

* This really ought to just drive a library for the torrent file creation?
* Needs to handle the RSS side of things.
* Need to generate the short witness proofs?
* Need to avoid partial tiles and figure out how to do the splitting in a perfect way. Memory: Power of two sized subtrees remain invariant?

## Testing

* Need to test the overall struct?
* Simple as writing a test script for verifying a bunch of random inclusions?
tar --zstd -cf test/archive.tar.zst test/tile
tar -cf test/archive.tar test/tile
tar -czf - test/tile | gzip -9 > test/archive.tar.gz
tar -cf - test/tile | zstd --ultra -22 --long=31 --threads=0 -o test/archive-max.tar.zst

du -sh test/tile
du -h test/archive.tar
du -h test/archive.tar.gz
du -h test/archive.tar.zst
du -h test/archive-max.tar.zst
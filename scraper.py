

# Tiles are served as at
#     <monitoring prefix>/tile/<L>/<N>[.p/<W>]
# with `Content-Type: application/octet-stream`.
# `<L>` is the “level” of the tile, and MUST be a decimal ASCII integer between 0
# and 5, with no additional leading zeroes.
# `<N>` is the index of the tile within the level. It MUST be a non-negative
# integer encoded into 3-digit path elements. All but the last path element MUST
# begin with an `x`. For example, index 1234067 will be encoded as
# `x001/x234/067`.

def get_hash_tile_paths(startEntry, endEntry):
    """
    Generate tile paths for entries between startEntry and endEntry (inclusive).

    Each tile contains 2^8 = 256 entries. The tile index is calculated as
    entry_index // 256.

    Args:
        startEntry: The first entry index to include
        endEntry: The last entry index to include

    Yields:
        Tile paths in the format 'x001/x234/067'
    """
    # Calculate the tile indices for the start and end entries
    start_tile = startEntry // 256
    end_tile = endEntry // 256

    # Generate paths for all tiles between start_tile and end_tile (inclusive)
    for tile_index in range(start_tile, end_tile + 1):
        # Convert the tile index to a string representation
        tile_str = str(tile_index).zfill(9)  # Pad to 9 digits

        # Format as x001/x234/067
        path = f"tile/x{tile_str[0:3]}/x{tile_str[3:6]}/{tile_str[6:9]}"

        yield path

# The log entries are served as a “data tile” at

#     <monitoring prefix>/tile/data/<N>[.p/<W>]

def get_data_tile_paths(startEntry, endEntry):
    """
    Generate data tile paths for entries between startEntry and endEntry (inclusive).

    Data tiles are served at <monitoring prefix>/tile/data/<N> where:
    - <N> is the index encoded as x001/x234/067

    Args:
        startEntry: The first entry index to include
        endEntry: The last entry index to include

    Yields:
        Tile paths in the format 'data/x001/x234/067'
    """
    # Calculate the tile indices for the start and end entries
    start_tile = startEntry // 256
    end_tile = endEntry // 256

    # Generate paths for all tiles between start_tile and end_tile (inclusive)
    for tile_index in range(start_tile, end_tile + 1):
        # Convert the tile index to a string representation
        tile_str = str(tile_index).zfill(9)  # Pad to 9 digits

        # Format as data/x001/x234/067
        path = f"tile/data/x{tile_str[0:3]}/x{tile_str[3:6]}/{tile_str[6:9]}"

        yield path

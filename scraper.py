

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
    Generate hash tile paths for entries between startEntry and endEntry (inclusive).

    Each tile contains 2^8 = 256 entries. The tile index is calculated as
    entry_index // 256.
    
    Hash tiles are served at <monitoring prefix>/tile/<L>/<N> where:
    - <L> is the level (0-5)
    - <N> is the index encoded as x001/x234/067
    
    Higher levels only have entries if lower levels are full. For example,
    level 1 only has entries if level 0 has at least 2^8 entries.

    Args:
        startEntry: The first entry index to include
        endEntry: The last entry index to include

    Yields:
        Tile paths for each level in the format 'tile/level/x001/x234/067'
    """
    # Calculate the tile indices for the start and end entries
    start_tile = startEntry // 256
    end_tile = endEntry // 256
    
    # Maximum possible level based on the end entry
    max_level = 0
    entries = endEntry + 1  # +1 because endEntry is inclusive
    while entries > 256:
        max_level += 1
        entries = (entries + 255) // 256  # Ceiling division by 256
    
    max_level = min(max_level, 5)  # Cap at level 5
    
    # For each valid level
    for level in range(max_level + 1):
        # At each level, the tile size increases by a factor of 256
        level_tile_size = 256 ** (level + 1)
        level_tile_count = 256 ** level
        
        # Calculate the tile indices for this level
        level_start_tile = start_tile // level_tile_count
        level_end_tile = end_tile // level_tile_count
        
        # Generate paths for all tiles between level_start_tile and level_end_tile (inclusive)
        for tile_index in range(level_start_tile, level_end_tile + 1):
            # Convert the tile index to a string representation
            tile_str = str(tile_index).zfill(9)  # Pad to 9 digits
            
            # Format as tile/level/x001/x234/067
            path = f"tile/{level}/x{tile_str[0:3]}/x{tile_str[3:6]}/{tile_str[6:9]}"
            
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

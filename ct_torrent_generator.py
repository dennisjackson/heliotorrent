#!/usr/bin/env python3
"""
Static CT Log Torrent Generator

This script generates torrent files for a local mirror of a Static CT log.
It organizes the log data into non-overlapping torrent files, each containing
entries, hashes, and a suitable checkpoint for a portion of the tree.
"""

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import os
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import bencodepy  # For creating torrent files


@dataclass
class TorrentConfig:
    """Configuration for torrent generation."""
    piece_length: int = 1024 * 1024  # 1MB pieces by default
    announce: str = "udp://tracker.opentrackr.org:1337/announce"
    announce_list: List[List[str]] = None
    comment: str = "Certificate Transparency Log Mirror"
    created_by: str = "CT Torrent Generator"
    private: bool = False
    source: str = "CT Log"


class CTTorrentGenerator:
    """Generates torrent files for a Static CT log mirror."""

    def __init__(self, log_dir: str, output_dir: str, config: TorrentConfig = None):
        """
        Initialize the torrent generator.
        
        Args:
            log_dir: Path to the local mirror of the Static CT log
            output_dir: Directory to save generated torrent files
            config: Torrent configuration
        """
        self.log_dir = Path(log_dir)
        self.output_dir = Path(output_dir)
        self.config = config or TorrentConfig()
        
        if not self.log_dir.exists():
            raise ValueError(f"Log directory {log_dir} does not exist")
        
        if not self.output_dir.exists():
            os.makedirs(self.output_dir)
        
        # Default announce list if none provided
        if not self.config.announce_list:
            self.config.announce_list = [
                ["udp://tracker.opentrackr.org:1337/announce"],
                ["udp://open.tracker.cl:1337/announce"],
                ["udp://tracker.openbittorrent.com:6969/announce"]
            ]

    def _get_checkpoint_path(self) -> Path:
        """Get the path to the checkpoint file."""
        checkpoint_path = self.log_dir / "checkpoint"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found at {checkpoint_path}")
        return checkpoint_path

    def _parse_checkpoint(self, checkpoint_path: Path) -> Tuple[int, str]:
        """
        Parse the checkpoint file to get the log size and hash.
        
        Returns:
            Tuple of (log_size, log_hash_hex)
        """
        with open(checkpoint_path, 'r') as f:
            lines = f.read().strip().split('\n')
            if len(lines) < 2:
                raise ValueError("Invalid checkpoint format")
            
            log_size = int(lines[0])
            log_hash_hex = lines[1]
            
            return log_size, log_hash_hex

    def _get_tile_paths(self) -> Dict[str, List[Path]]:
        """
        Get all tile paths organized by level.
        
        Returns:
            Dictionary mapping level to list of tile paths
        """
        tile_paths = {}
        tile_dir = self.log_dir / "tile"
        
        if not tile_dir.exists():
            raise FileNotFoundError(f"Tile directory not found at {tile_dir}")
        
        # Get all level directories
        for level_dir in tile_dir.iterdir():
            if level_dir.is_dir() and level_dir.name.isdigit():
                level = level_dir.name
                tile_paths[level] = []
                
                # Recursively find all tiles in this level
                for root, _, files in os.walk(level_dir):
                    for file in files:
                        if not file.startswith('.'):  # Skip hidden files
                            tile_paths[level].append(Path(root) / file)
        
        # Add data tiles
        data_dir = tile_dir / "data"
        if data_dir.exists():
            tile_paths["data"] = []
            for root, _, files in os.walk(data_dir):
                for file in files:
                    if not file.startswith('.'):
                        tile_paths["data"].append(Path(root) / file)
        
        return tile_paths

    def _get_issuer_paths(self) -> List[Path]:
        """Get all issuer certificate paths."""
        issuer_paths = []
        issuer_dir = self.log_dir / "issuer"
        
        if not issuer_dir.exists():
            return []  # Issuer directory might not exist yet
        
        for root, _, files in os.walk(issuer_dir):
            for file in files:
                if not file.startswith('.'):
                    issuer_paths.append(Path(root) / file)
        
        return issuer_paths

    def _create_torrent_for_range(self, start_idx: int, end_idx: int, 
                                 log_size: int, log_hash: str,
                                 tile_paths: Dict[str, List[Path]], 
                                 issuer_paths: List[Path]) -> str:
        """
        Create a torrent file for a specific range of the log.
        
        Args:
            start_idx: Start index of the range
            end_idx: End index of the range
            log_size: Total size of the log
            log_hash: Hash of the log
            tile_paths: Dictionary of tile paths by level
            issuer_paths: List of issuer certificate paths
            
        Returns:
            Path to the created torrent file
        """
        # Create a temporary directory for this range
        range_dir = self.output_dir / f"ct_log_{start_idx}_{end_idx}"
        if range_dir.exists():
            import shutil
            shutil.rmtree(range_dir)
        os.makedirs(range_dir)
        
        # Create a custom checkpoint for this range
        with open(self._get_checkpoint_path(), 'r') as f:
            checkpoint_content = f.read().strip().split('\n')
        
        # Modify the checkpoint to reflect this range
        checkpoint_content[0] = str(end_idx - start_idx)
        
        with open(range_dir / "checkpoint", 'w') as f:
            f.write('\n'.join(checkpoint_content))
        
        # Copy relevant tiles
        for level, paths in tile_paths.items():
            level_dir = range_dir / "tile" / level
            os.makedirs(level_dir, exist_ok=True)
            
            for tile_path in paths:
                # Determine if this tile is relevant for our range
                if level == "data":
                    # For data tiles, check if they contain entries in our range
                    tile_idx = self._extract_tile_index(tile_path)
                    tile_start = tile_idx * 256
                    tile_end = tile_start + 256
                    
                    if tile_end <= start_idx or tile_start >= end_idx:
                        continue  # Skip tiles outside our range
                
                # Create the directory structure
                rel_path = tile_path.relative_to(self.log_dir / "tile" / level)
                target_dir = level_dir / rel_path.parent
                os.makedirs(target_dir, exist_ok=True)
                
                # Copy the file
                with open(tile_path, 'rb') as src, open(target_dir / rel_path.name, 'wb') as dst:
                    dst.write(src.read())
        
        # Copy relevant issuer certificates
        if issuer_paths:
            issuer_dir = range_dir / "issuer"
            os.makedirs(issuer_dir, exist_ok=True)
            
            for issuer_path in issuer_paths:
                # Copy all issuers for now - in a real implementation we would
                # only copy the ones referenced by entries in our range
                rel_path = issuer_path.relative_to(self.log_dir / "issuer")
                with open(issuer_path, 'rb') as src, open(issuer_dir / rel_path, 'wb') as dst:
                    dst.write(src.read())
        
        # Create the torrent file
        torrent_file = self._create_torrent(
            range_dir, 
            f"ct_log_{start_idx}_{end_idx}.torrent",
            f"CT Log Entries {start_idx}-{end_idx} of {log_size}"
        )
        
        return torrent_file

    def _extract_tile_index(self, tile_path: Path) -> int:
        """
        Extract the index from a tile path.
        
        Args:
            tile_path: Path to a tile file
            
        Returns:
            The index of the tile
        """
        # Parse the path components to extract the index
        # Format is like: tile/data/x001/x234/067 or tile/data/x001/x234/067.p/123
        parts = list(tile_path.parts)
        
        # Remove the tile and level parts
        parts = parts[parts.index("tile") + 2:]
        
        # Handle partial tiles
        if ".p" in parts[-1]:
            parts[-1] = parts[-1].split(".p")[0]
        
        # Reconstruct the index
        index_str = ""
        for part in parts:
            if part.startswith("x"):
                index_str += part[1:]
            else:
                index_str += part
        
        return int(index_str)

    def _create_torrent(self, content_dir: Path, torrent_name: str, comment: str) -> str:
        """
        Create a torrent file for the given content.
        
        Args:
            content_dir: Directory containing the content
            torrent_name: Name of the torrent file
            comment: Comment for the torrent
            
        Returns:
            Path to the created torrent file
        """
        torrent_path = self.output_dir / torrent_name
        
        # Calculate piece hashes
        piece_length = self.config.piece_length
        pieces = b""
        
        # Get all files in the directory
        files = []
        for root, _, filenames in os.walk(content_dir):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append({
                    'path': os.path.relpath(file_path, content_dir).split(os.sep),
                    'length': os.path.getsize(file_path)
                })
        
        # Sort files for deterministic ordering
        files.sort(key=lambda x: '/'.join(x['path']))
        
        # Calculate pieces
        current_piece = b""
        for file_info in files:
            file_path = os.path.join(content_dir, *file_info['path'])
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(piece_length - len(current_piece))
                    if not data:
                        break
                    
                    current_piece += data
                    if len(current_piece) == piece_length:
                        pieces += hashlib.sha1(current_piece).digest()
                        current_piece = b""
        
        # Add the last piece if there is one
        if current_piece:
            pieces += hashlib.sha1(current_piece).digest()
        
        # Create the torrent dictionary
        torrent_dict = {
            'announce': self.config.announce,
            'announce-list': self.config.announce_list,
            'comment': comment,
            'created by': self.config.created_by,
            'creation date': int(time.time()),
            'info': {
                'files': files,
                'name': os.path.basename(content_dir),
                'piece length': piece_length,
                'pieces': pieces,
                'private': 1 if self.config.private else 0,
                'source': self.config.source
            }
        }
        
        # Write the torrent file
        with open(torrent_path, 'wb') as f:
            f.write(bencodepy.encode(torrent_dict))
        
        return str(torrent_path)

    def generate_torrents(self, entries_per_torrent: int = 100000) -> List[str]:
        """
        Generate torrent files for the log.
        
        Args:
            entries_per_torrent: Number of entries per torrent
            
        Returns:
            List of paths to the created torrent files
        """
        # Parse the checkpoint to get the log size
        checkpoint_path = self._get_checkpoint_path()
        log_size, log_hash = self._parse_checkpoint(checkpoint_path)
        
        # Get all tile and issuer paths
        tile_paths = self._get_tile_paths()
        issuer_paths = self._get_issuer_paths()
        
        # Calculate the number of torrents needed
        num_torrents = (log_size + entries_per_torrent - 1) // entries_per_torrent
        
        # Create a torrent for each range
        torrent_files = []
        for i in range(num_torrents):
            start_idx = i * entries_per_torrent
            end_idx = min((i + 1) * entries_per_torrent, log_size)
            
            torrent_file = self._create_torrent_for_range(
                start_idx, end_idx, log_size, log_hash, tile_paths, issuer_paths
            )
            
            torrent_files.append(torrent_file)
            print(f"Created torrent {i+1}/{num_torrents}: {torrent_file}")
        
        return torrent_files


def main():
    parser = argparse.ArgumentParser(description='Generate torrent files for a Static CT log mirror')
    parser.add_argument('log_dir', help='Path to the local mirror of the Static CT log')
    parser.add_argument('--output-dir', '-o', default='./torrents', help='Directory to save generated torrent files')
    parser.add_argument('--entries-per-torrent', '-e', type=int, default=100000, 
                        help='Number of entries per torrent (default: 100000)')
    parser.add_argument('--piece-length', '-p', type=int, default=1024*1024, 
                        help='Torrent piece length in bytes (default: 1MB)')
    parser.add_argument('--announce', '-a', 
                        default='udp://tracker.opentrackr.org:1337/announce',
                        help='Primary tracker announce URL')
    parser.add_argument('--private', action='store_true', 
                        help='Set the private flag in the torrent')
    
    args = parser.parse_args()
    
    # Create torrent config
    config = TorrentConfig(
        piece_length=args.piece_length,
        announce=args.announce,
        private=args.private
    )
    
    # Generate torrents
    generator = CTTorrentGenerator(args.log_dir, args.output_dir, config)
    torrent_files = generator.generate_torrents(args.entries_per_torrent)
    
    print(f"\nGenerated {len(torrent_files)} torrent files in {args.output_dir}")


if __name__ == "__main__":
    main()

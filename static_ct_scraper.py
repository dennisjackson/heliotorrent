#!/usr/bin/env python3
"""
Static CT Log Scraper

This script scrapes a Certificate Transparency log that implements the Static CT API
as defined in https://c2sp.org/static-ct-api.

It fetches checkpoints, tiles, and log entries in parallel to efficiently monitor the log.
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
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import cryptography.hazmat.primitives.asymmetric.ec as ec
import cryptography.hazmat.primitives.hashes as hashes
import cryptography.hazmat.primitives.serialization as serialization
from cryptography import x509


@dataclass
class Checkpoint:
    """Represents a CT log checkpoint."""
    size: int
    hash: bytes
    timestamp: int
    signature: bytes
    origin: str


@dataclass
class TileLeaf:
    """Represents a leaf entry in a data tile."""
    timestamp: int
    entry_type: int
    leaf_cert: bytes
    pre_cert: Optional[bytes]
    issuer_key_hash: bytes
    cert_chain_fingerprints: List[bytes]


class StaticCTScraper:
    """A scraper for Static CT logs."""

    def __init__(self, monitoring_prefix: str, output_dir: str = None):
        """
        Initialize the scraper.
        
        Args:
            monitoring_prefix: The monitoring prefix URL of the log
            output_dir: Directory to save downloaded certificates
        """
        self.monitoring_prefix = monitoring_prefix.rstrip('/')
        self.output_dir = output_dir
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    async def fetch_checkpoint(self) -> Checkpoint:
        """Fetch and parse the latest checkpoint."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.monitoring_prefix}/checkpoint") as response:
                response.raise_for_status()
                text = await response.text()
                
                lines = text.strip().split('\n')
                if len(lines) < 4:
                    raise ValueError("Invalid checkpoint format")
                
                # Parse checkpoint
                size = int(lines[0])
                hash_hex = lines[1]
                origin = lines[2]
                
                # Parse signature
                sig_parts = lines[3].split(' ')
                if len(sig_parts) != 3:
                    raise ValueError("Invalid signature format")
                
                # Extract timestamp and signature from the signature data
                sig_data = base64.b64decode(sig_parts[2])
                timestamp, = struct.unpack('>Q', sig_data[:8])
                signature = sig_data[8:]
                
                return Checkpoint(
                    size=size,
                    hash=binascii.unhexlify(hash_hex),
                    timestamp=timestamp,
                    signature=signature,
                    origin=origin
                )

    async def fetch_tile(self, level: int, index: int, partial_width: Optional[int] = None) -> bytes:
        """
        Fetch a Merkle tree tile.
        
        Args:
            level: The level of the tile (0-5)
            index: The index of the tile
            partial_width: Width of partial tile (1-255) if applicable
            
        Returns:
            The raw tile data
        """
        # Format the index as path components
        index_str = f"{index:09d}"
        path_components = []
        for i in range(0, len(index_str), 3):
            component = index_str[i:i+3]
            if i < len(index_str) - 3:
                component = 'x' + component
            path_components.append(component)
        
        index_path = '/'.join(path_components)
        
        # Construct the URL
        url = f"{self.monitoring_prefix}/tile/{level}/{index_path}"
        if partial_width is not None:
            url += f".p/{partial_width}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.read()

    async def fetch_data_tile(self, index: int, partial_width: Optional[int] = None) -> bytes:
        """
        Fetch a data tile.
        
        Args:
            index: The index of the tile
            partial_width: Width of partial tile (1-255) if applicable
            
        Returns:
            The raw data tile
        """
        # Format the index as path components
        index_str = f"{index:09d}"
        path_components = []
        for i in range(0, len(index_str), 3):
            component = index_str[i:i+3]
            if i < len(index_str) - 3:
                component = 'x' + component
            path_components.append(component)
        
        index_path = '/'.join(path_components)
        
        # Construct the URL
        url = f"{self.monitoring_prefix}/tile/data/{index_path}"
        if partial_width is not None:
            url += f".p/{partial_width}"
        
        headers = {'Accept-Encoding': 'gzip, identity'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.read()

    async def fetch_issuer(self, fingerprint: bytes) -> bytes:
        """
        Fetch an issuer certificate.
        
        Args:
            fingerprint: SHA-256 hash of the issuer certificate
            
        Returns:
            The raw certificate data
        """
        fingerprint_hex = fingerprint.hex()
        url = f"{self.monitoring_prefix}/issuer/{fingerprint_hex}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                cert_data = await response.read()
                
                # Save the certificate if output directory is specified
                if self.output_dir:
                    cert_path = os.path.join(self.output_dir, f"issuer_{fingerprint_hex}.der")
                    with open(cert_path, 'wb') as f:
                        f.write(cert_data)
                
                return cert_data

    def parse_data_tile(self, data: bytes) -> List[TileLeaf]:
        """
        Parse a data tile into individual leaf entries.
        
        Args:
            data: Raw data tile bytes
            
        Returns:
            List of parsed TileLeaf objects
        """
        results = []
        offset = 0
        
        while offset < len(data):
            # Parse TimestampedEntry
            timestamp, = struct.unpack('>Q', data[offset:offset+8])
            offset += 8
            
            entry_type, = struct.unpack('>B', data[offset:offset+1])
            offset += 1
            
            if entry_type == 0:  # x509_entry
                cert_len, = struct.unpack('>I', b'\x00' + data[offset:offset+3])
                offset += 3
                leaf_cert = data[offset:offset+cert_len]
                offset += cert_len
                pre_cert = None
                
            elif entry_type == 1:  # precert_entry
                issuer_key_hash = data[offset:offset+32]
                offset += 32
                
                tbs_len, = struct.unpack('>I', b'\x00' + data[offset:offset+3])
                offset += 3
                leaf_cert = data[offset:offset+tbs_len]  # TBSCertificate
                offset += tbs_len
                
                # Parse the pre-certificate
                precert_len, = struct.unpack('>I', b'\x00' + data[offset:offset+3])
                offset += 3
                pre_cert = data[offset:offset+precert_len]
                offset += precert_len
            else:
                raise ValueError(f"Unknown entry type: {entry_type}")
            
            # Parse certificate chain fingerprints
            chain_len, = struct.unpack('>H', data[offset:offset+2])
            offset += 2
            
            cert_chain_fingerprints = []
            for _ in range(chain_len):
                fingerprint = data[offset:offset+32]
                cert_chain_fingerprints.append(fingerprint)
                offset += 32
            
            leaf = TileLeaf(
                timestamp=timestamp,
                entry_type=entry_type,
                leaf_cert=leaf_cert,
                pre_cert=pre_cert,
                issuer_key_hash=issuer_key_hash if entry_type == 1 else None,
                cert_chain_fingerprints=cert_chain_fingerprints
            )
            results.append(leaf)
        
        return results

    async def scrape_log(self, max_entries: Optional[int] = None) -> None:
        """
        Scrape the log, fetching entries in parallel.
        
        Args:
            max_entries: Maximum number of entries to fetch (None for all)
        """
        # Fetch the checkpoint
        checkpoint = await self.fetch_checkpoint()
        print(f"Log size: {checkpoint.size} entries")
        print(f"Log hash: {checkpoint.hash.hex()}")
        print(f"Timestamp: {checkpoint.timestamp}")
        print(f"Origin: {checkpoint.origin}")
        
        # Determine how many entries to fetch
        entries_to_fetch = min(checkpoint.size, max_entries) if max_entries else checkpoint.size
        print(f"Fetching {entries_to_fetch} entries...")
        
        # Calculate how many tiles we need
        full_tiles = entries_to_fetch // 256
        partial_width = entries_to_fetch % 256
        
        # Prepare tasks for fetching data tiles
        tasks = []
        for i in range(full_tiles):
            tasks.append(self.fetch_data_tile(i))
        
        if partial_width > 0:
            tasks.append(self.fetch_data_tile(full_tiles, partial_width))
        
        # Fetch all tiles in parallel
        data_tiles = await asyncio.gather(*tasks)
        
        # Process the tiles
        all_leaves = []
        for i, tile_data in enumerate(data_tiles):
            leaves = self.parse_data_tile(tile_data)
            all_leaves.extend(leaves)
            print(f"Processed tile {i} with {len(leaves)} entries")
        
        print(f"Total entries processed: {len(all_leaves)}")
        
        # Fetch issuers for the first few entries as an example
        issuer_fingerprints = set()
        for leaf in all_leaves[:min(10, len(all_leaves))]:
            for fingerprint in leaf.cert_chain_fingerprints:
                issuer_fingerprints.add(fingerprint)
        
        print(f"Fetching {len(issuer_fingerprints)} unique issuers...")
        issuer_tasks = [self.fetch_issuer(fingerprint) for fingerprint in issuer_fingerprints]
        issuers = await asyncio.gather(*issuer_tasks)
        
        print(f"Fetched {len(issuers)} issuer certificates")


async def main():
    parser = argparse.ArgumentParser(description='Scrape a Static CT log')
    parser.add_argument('monitoring_prefix', help='The monitoring prefix URL of the log')
    parser.add_argument('--output-dir', '-o', help='Directory to save certificates')
    parser.add_argument('--max-entries', '-m', type=int, help='Maximum number of entries to fetch')
    
    args = parser.parse_args()
    
    scraper = StaticCTScraper(args.monitoring_prefix, args.output_dir)
    await scraper.scrape_log(args.max_entries)


if __name__ == "__main__":
    asyncio.run(main())

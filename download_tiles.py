#!/usr/bin/env python3
"""
Tile downloader for Ukraine Fire Tracking System.
Downloads OpenStreetMap tiles for offline use at multiple zoom levels.
"""

import os
import requests
import time
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List
import config


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """
    Convert latitude/longitude to tile numbers for given zoom level.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees  
        zoom: Zoom level
        
    Returns:
        Tuple of (x, y) tile coordinates
    """
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lat_lon(x: int, y: int, zoom: int) -> Tuple[float, float]:
    """
    Convert tile coordinates to latitude/longitude.
    
    Args:
        x: Tile X coordinate
        y: Tile Y coordinate
        zoom: Zoom level
        
    Returns:
        Tuple of (lat, lon) in decimal degrees
    """
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def calculate_tile_bounds(north: float, south: float, east: float, west: float, zoom: int) -> Tuple[int, int, int, int]:
    """
    Calculate tile boundaries for a geographic region.
    
    Args:
        north, south, east, west: Geographic bounds in decimal degrees
        zoom: Zoom level
        
    Returns:
        Tuple of (x_min, y_min, x_max, y_max) tile coordinates
    """
    # Get tile coordinates for corners
    x_west, y_north = lat_lon_to_tile(north, west, zoom)
    x_east, y_south = lat_lon_to_tile(south, east, zoom)
    
    # Ensure proper ordering
    x_min = min(x_west, x_east)
    x_max = max(x_west, x_east)
    y_min = min(y_north, y_south)
    y_max = max(y_north, y_south)
    
    return x_min, y_min, x_max, y_max


def download_tile(server_url: str, zoom: int, x: int, y: int, output_dir: str) -> bool:
    """
    Download a single tile from OSM server.
    
    Args:
        server_url: Base URL of tile server
        zoom: Zoom level
        x, y: Tile coordinates
        output_dir: Directory to save tile
        
    Returns:
        True if successful, False otherwise
    """
    # Create directory structure
    tile_dir = os.path.join(output_dir, str(zoom), str(x))
    os.makedirs(tile_dir, exist_ok=True)
    
    tile_path = os.path.join(tile_dir, f"{y}.png")
    
    # Skip if already exists
    if os.path.exists(tile_path) and os.path.getsize(tile_path) > 0:
        return True
    
    # Build URL
    url = f"{server_url}/{zoom}/{x}/{y}.png"
    
    try:
        headers = {
            'User-Agent': 'Ukraine Fire Tracking System/1.0 (Educational Research Project)'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            with open(tile_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"    Failed to download {zoom}/{x}/{y}: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"    Error downloading {zoom}/{x}/{y}: {e}")
        return False


class TileDownloader:
    """Manages downloading tiles for multiple zoom levels."""
    
    def __init__(self):
        """Initialize tile downloader."""
        self.servers = config.OSM_TILE_SERVERS
        self.current_server = 0
        self.output_dir = config.TILE_DIRECTORY
        self.delay = config.TILE_DOWNLOAD_DELAY
        self.max_workers = config.MAX_DOWNLOAD_THREADS
        
        # Ensure output directory exists
        config.ensure_directories()
    
    def get_next_server(self) -> str:
        """Get next server URL for round-robin load balancing."""
        server = self.servers[self.current_server]
        self.current_server = (self.current_server + 1) % len(self.servers)
        return server
    
    def estimate_tiles(self, zoom_levels: List[int]) -> dict:
        """
        Estimate number of tiles needed for each zoom level.
        
        Args:
            zoom_levels: List of zoom levels to download
            
        Returns:
            Dictionary mapping zoom level to tile count
        """
        bounds = config.BOUNDING_BOX
        estimates = {}
        
        for zoom in zoom_levels:
            x_min, y_min, x_max, y_max = calculate_tile_bounds(
                bounds['north'], bounds['south'], 
                bounds['east'], bounds['west'], 
                zoom
            )
            
            tile_count = (x_max - x_min + 1) * (y_max - y_min + 1)
            estimates[zoom] = tile_count
        
        return estimates
    
    def download_zoom_level(self, zoom: int) -> bool:
        """
        Download all tiles for a specific zoom level.
        
        Args:
            zoom: Zoom level to download
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Downloading tiles for zoom level {zoom}")
        print(f"{'='*60}")
        
        bounds = config.BOUNDING_BOX
        x_min, y_min, x_max, y_max = calculate_tile_bounds(
            bounds['north'], bounds['south'],
            bounds['east'], bounds['west'],
            zoom
        )
        
        total_tiles = (x_max - x_min + 1) * (y_max - y_min + 1)
        
        print(f"Tile bounds: X({x_min}-{x_max}), Y({y_min}-{y_max})")
        print(f"Total tiles to download: {total_tiles}")
        
        # Generate list of all tiles to download
        tile_list = []
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tile_list.append((zoom, x, y))
        
        # Filter out existing tiles
        remaining_tiles = []
        for zoom_level, x, y in tile_list:
            tile_path = os.path.join(self.output_dir, str(zoom_level), str(x), f"{y}.png")
            if not os.path.exists(tile_path) or os.path.getsize(tile_path) == 0:
                remaining_tiles.append((zoom_level, x, y))
        
        if not remaining_tiles:
            print(f"All tiles already downloaded for zoom level {zoom}")
            return True
        
        print(f"Need to download {len(remaining_tiles)} tiles (skipping {total_tiles - len(remaining_tiles)} existing)")
        
        # Download tiles with progress tracking
        downloaded = 0
        failed = 0
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit download tasks
            future_to_tile = {}
            for zoom_level, x, y in remaining_tiles:
                server_url = self.get_next_server()
                future = executor.submit(download_tile, server_url, zoom_level, x, y, self.output_dir)
                future_to_tile[future] = (zoom_level, x, y)
                
                # Add delay between submissions to be respectful
                time.sleep(self.delay / self.max_workers)
            
            # Process completed downloads
            for future in as_completed(future_to_tile):
                zoom_level, x, y = future_to_tile[future]
                
                try:
                    success = future.result()
                    if success:
                        downloaded += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"    Exception downloading {zoom_level}/{x}/{y}: {e}")
                    failed += 1
                
                # Progress update
                total_processed = downloaded + failed
                if total_processed % 100 == 0 or total_processed == len(remaining_tiles):
                    progress = (total_processed / len(remaining_tiles)) * 100
                    print(f"  Progress: {total_processed}/{len(remaining_tiles)} "
                          f"({progress:.1f}%) - Downloaded: {downloaded}, Failed: {failed}")
        
        print(f"\nZoom level {zoom} complete!")
        print(f"Successfully downloaded: {downloaded}")
        print(f"Failed: {failed}")
        
        return failed == 0
    
    def download_all_levels(self, zoom_levels: List[int] = None) -> bool:
        """
        Download tiles for all specified zoom levels.
        
        Args:
            zoom_levels: List of zoom levels to download (default: from config)
            
        Returns:
            True if all downloads successful
        """
        if zoom_levels is None:
            zoom_levels = config.ZOOM_LEVELS
        
        print("Ukraine Fire Tracking System - Tile Downloader")
        print("=" * 60)
        print(f"Geographic region: {config.BOUNDING_BOX}")
        print(f"Zoom levels: {zoom_levels}")
        print(f"Output directory: {self.output_dir}")
        print(f"Max concurrent downloads: {self.max_workers}")
        print(f"Delay between requests: {self.delay}s")
        
        # Estimate total tiles
        estimates = self.estimate_tiles(zoom_levels)
        total_estimate = sum(estimates.values())
        
        print(f"\nEstimated tiles per zoom level:")
        for zoom, count in estimates.items():
            print(f"  Zoom {zoom}: ~{count} tiles")
        print(f"Total estimated tiles: ~{total_estimate}")
        
        # Calculate estimated download time
        estimated_time_minutes = (total_estimate * self.delay) / 60
        print(f"Estimated download time: ~{estimated_time_minutes:.1f} minutes")
        
        # Auto-proceed for now (can be made interactive later)
        print(f"\nProceeding with download...")
        # response = input(f"\nProceed with download? (y/N): ")
        # if response.lower() != 'y':
        #     print("Download cancelled.")
        #     return False
        
        start_time = time.time()
        success = True
        
        # Download each zoom level
        for zoom in sorted(zoom_levels):
            zoom_success = self.download_zoom_level(zoom)
            if not zoom_success:
                print(f"Warning: Some tiles failed to download for zoom level {zoom}")
                success = False
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n{'='*60}")
        print(f"Download Complete!")
        print(f"{'='*60}")
        print(f"Total time: {total_time/60:.1f} minutes")
        print(f"Output directory: {self.output_dir}")
        
        # Verify downloads
        self.verify_downloads(zoom_levels)
        
        return success
    
    def verify_downloads(self, zoom_levels: List[int]):
        """
        Verify downloaded tiles and report statistics.
        
        Args:
            zoom_levels: List of zoom levels to verify
        """
        print(f"\nVerifying downloads...")
        
        for zoom in zoom_levels:
            zoom_dir = os.path.join(self.output_dir, str(zoom))
            if not os.path.exists(zoom_dir):
                print(f"  Zoom {zoom}: Directory not found")
                continue
            
            # Count tiles
            tile_count = 0
            for x_dir in os.listdir(zoom_dir):
                x_path = os.path.join(zoom_dir, x_dir)
                if os.path.isdir(x_path):
                    for tile_file in os.listdir(x_path):
                        if tile_file.endswith('.png'):
                            tile_path = os.path.join(x_path, tile_file)
                            if os.path.getsize(tile_path) > 0:
                                tile_count += 1
            
            # Calculate expected tiles
            bounds = config.BOUNDING_BOX
            x_min, y_min, x_max, y_max = calculate_tile_bounds(
                bounds['north'], bounds['south'],
                bounds['east'], bounds['west'],
                zoom
            )
            expected = (x_max - x_min + 1) * (y_max - y_min + 1)
            
            print(f"  Zoom {zoom}: {tile_count}/{expected} tiles "
                  f"({tile_count/expected*100:.1f}%)")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Specific zoom levels provided
        try:
            zoom_levels = [int(z) for z in sys.argv[1:]]
            print(f"Downloading zoom levels: {zoom_levels}")
        except ValueError:
            print("Error: Invalid zoom level. Use integers only.")
            sys.exit(1)
    else:
        # Use default zoom levels from config
        zoom_levels = config.ZOOM_LEVELS
    
    # Validate zoom levels
    if any(z < 1 or z > 18 for z in zoom_levels):
        print("Error: Zoom levels must be between 1 and 18")
        sys.exit(1)
    
    # Create downloader and run
    downloader = TileDownloader()
    success = downloader.download_all_levels(zoom_levels)
    
    if success:
        print("\nTile download completed successfully!")
        print("You can now run the application offline.")
    else:
        print("\nTile download completed with some errors.")
        print("Check the output above for failed downloads.")
        sys.exit(1)


if __name__ == "__main__":
    main()
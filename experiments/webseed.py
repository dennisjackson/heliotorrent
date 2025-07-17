import argparse
import glob
import os
import subprocess
from tqdm import tqdm

def find_torrent_files(directory):
    """Recursively finds all .torrent files in a directory."""
    pattern = os.path.join(directory, "**", "*.torrent")
    return glob.glob(pattern, recursive=True)

def main():
    parser = argparse.ArgumentParser(
        description="Recursively update web seed URLs in .torrent files.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example:\npython experiments/webseed.py torrents/ http://seed.example.com/torrents,http://another.seed.com/"
    )
    parser.add_argument("directory", help="The directory to search for .torrent files.")
    parser.add_argument("urls", help="A comma-separated list of web seed URLs.")
    args = parser.parse_args()

    urls = [url.strip() for url in args.urls.split(',')]

    if not os.path.isdir(args.directory):
        print(f"Error: Directory not found at '{args.directory}'")
        return

    torrent_files = glob.glob(os.path.join(args.directory, "**", "*.torrent"),recursive=True)

    if not torrent_files:
        print(f"No .torrent files found in '{args.directory}'")
        return

    print(f"Found {len(torrent_files)} .torrent files. Updating web seeds...")

    for torrent_file in tqdm(torrent_files):
        command = ["torrentfile", "edit", torrent_file, "--web-seed"] + urls
        print(f"Processing: {torrent_file}")
        try:
            # The torrentfile library modifies the file in place.
            subprocess.run(command, check=True, capture_output=True, text=True)
            # print("  -> Successfully updated web seeds.")
        except subprocess.CalledProcessError as e:
            print(f"  -> Failed to update {os.path.basename(torrent_file)}:")
            print(f"     Command: {' '.join(command)}")
            print(f"     Error: {e.stderr.strip()}")
        except FileNotFoundError:
            print("Error: 'torrentfile' command not found. Make sure it's installed and in your PATH.")
            print("You can typically install it with: pip install torrentfile-cli")
            return

if __name__ == "__main__":
    main()
import argparse
import glob
import os
import subprocess
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def find_torrent_files(directory):
    """Recursively finds all .torrent files in a directory."""
    pattern = os.path.join(directory, "**", "*.torrent")
    return glob.glob(pattern, recursive=True)

def update_torrent_file(torrent_file, urls):
    """Updates a single torrent file with web seeds."""
    command = ["torrentfile", "edit", torrent_file, "--web-seed"] + urls
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return (torrent_file, True, None)
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to update {os.path.basename(torrent_file)}:\n"
        error_message += f"     Command: {' '.join(command)}\n"
        error_message += f"     Error: {e.stderr.strip()}"
        return (torrent_file, False, error_message)
    except FileNotFoundError:
        return (torrent_file, False, "Error: 'torrentfile' command not found. Make sure it's installed and in your PATH.\nYou can typically install it with: pip install torrentfile-cli")

def main():
    parser = argparse.ArgumentParser(
        description="Recursively update web seed URLs in .torrent files.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example:\npython experiments/webseed.py torrents/ http://seed.example.com/torrents,http://another.seed.com/"
    )
    parser.add_argument("directory", help="The directory to search for .torrent files.")
    parser.add_argument("urls", help="A comma-separated list of web seed URLs.")
    parser.add_argument("-w", "--workers", type=int, default=10, help="Number of parallel workers.")
    args = parser.parse_args()

    urls = [url.strip() for url in args.urls.split(',')]

    if not os.path.isdir(args.directory):
        print(f"Error: Directory not found at '{args.directory}'")
        return

    torrent_files = glob.glob(os.path.join(args.directory, "**", "*.torrent"),recursive=True)

    if not torrent_files:
        print(f"No .torrent files found in '{args.directory}'")
        return

    print(f"Found {len(torrent_files)} .torrent files. Updating web seeds with {args.workers} workers...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(update_torrent_file, torrent_file, urls) for torrent_file in torrent_files]

        for future in tqdm(as_completed(futures), total=len(torrent_files)):
            torrent_file, success, error_message = future.result()
            if not success:
                tqdm.write(f"  -> {error_message}")
                if error_message and "command not found" in error_message:
                    # No point in continuing if the command is not found.
                    # We can cancel remaining futures.
                    executor.shutdown(wait=False, cancel_futures=True)
                    break


if __name__ == "__main__":
    main()
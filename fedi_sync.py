import argparse
import time
import os
from relay_sync import RelaySyncer

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Relay URLs
RELAY_URL = "wss://relay.mostr.pub"
OUTPUT_RELAY = "wss://relay.nos.social"
LAST_RUN_FILE = os.path.join(SCRIPT_DIR, "last_ran_fedisync_timestamp.txt")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Fediverse to Nostr synchronization script.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    return parser.parse_args()

def get_pubkeys_from_file(filename="matching_nhex.txt"):
    try:
        full_path = os.path.join(SCRIPT_DIR, filename)
        with open(full_path, "r") as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"No pubkeys found in {filename}.")
        return []

def main():
    start_time = time.time()
    args = parse_arguments()

    syncer = RelaySyncer(
        input_relay=RELAY_URL,
        output_relay=OUTPUT_RELAY,
        timestamp_file=LAST_RUN_FILE,
        quiet_mode=args.quiet
    )

    pubkeys = get_pubkeys_from_file()
    if not pubkeys:
        return

    if not args.quiet:
        print("Fetching and publishing recent events from Nostr relay...")

    successful_syncs = syncer.fetch_and_publish_events(pubkeys)

    duration = time.time() - start_time
    print(f"- Number of Mastodon users fetched: {len(pubkeys)}")
    print(f"- Number of notes copied to relay.nos.social: {successful_syncs}")
    print(f"- Duration: {duration:.1f} seconds")

if __name__ == "__main__":
    main()

"""
This script connects to a Nostr relay to fetch metadata events and identifies
public keys associated with a specific identifier from Bluesky. The purpose
is to extract Nostr content for users that originate from Bluesky, using
the NIP-05 identifier. The matching public keys are saved to a file for
further use or analysis.
"""

import json
import os
from websocket import create_connection
import csv
import time as time_module
from datetime import datetime, timedelta, time as datetime_time
import traceback
import math
import argparse
import sys
import uuid

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
RELAY_URL = "wss://relay.mostr.pub"
TARGET_IDENTIFIER = "brid.gy_at_bsky"
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "matching_nhex.txt")
TIMESTAMP_FILE = os.path.join(SCRIPT_DIR, "last_ran_timestamp.txt")

# Load blocklist domains from the CSV file
def load_blocklist(file_path):
    blocklist = set()
    full_path = os.path.join(SCRIPT_DIR, file_path)
    with open(full_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            domain = row[0]
            blocklist.add(domain)
    return blocklist

# Extract domain from nip05 and check against blocklist
def is_domain_blocked(nip05, blocklist):
    if "@" in nip05:
        domain = nip05.split("@")[1]
        domain = domain.replace("-", ".")
        return domain in blocklist
    return False

# Read the last successful timestamp from a file
def read_last_successful_timestamp():
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, "r") as f:
            timestamp_str = f.read().strip()
            if timestamp_str and timestamp_str.isdigit():
                return datetime.fromtimestamp(int(timestamp_str))
    return None

# Update the timestamp file with the latest successful timestamp
def update_last_successful_timestamp(timestamp):
    """
    Update the timestamp file with the latest successful timestamp
    Args:
        timestamp: Either a datetime object or unix timestamp (int)
    """
    try:
        if isinstance(timestamp, int):
            # If we got an integer timestamp, just write it directly
            with open(TIMESTAMP_FILE, "w") as f:
                f.write(str(timestamp))
        else:
            # If we got a datetime object, convert to timestamp
            with open(TIMESTAMP_FILE, "w") as f:
                f.write(str(int(timestamp.timestamp())))

        if not is_tty():
            print(f"Updated timestamp file to: {timestamp}")
    except Exception as e:
        print(f"Error updating timestamp file: {e}")

# Function to check if the script is running in a TTY
def is_tty():
    return sys.stdout.isatty()

# Fetch kind: 0 metadata events from the relay
def fetch_metadata(blocklist, cron_mode=False):
    start_time = time_module.time()
    pubkeys = set()
    processed_event_ids = set()
    blocked_count = 0
    loop_counter = 0
    growth_factor = 0
    time_gap = timedelta(minutes=20)

    start_date = read_last_successful_timestamp() or datetime(2024, 5, 6)
    current_time = datetime.now()

    if not cron_mode:
        print(f"Starting time range: {start_date} to {current_time}")
        print(f"Last successful timestamp: {read_last_successful_timestamp()}")

    try:
        ws = create_connection(RELAY_URL)
        if not cron_mode:
            print(f"Connected to relay: {RELAY_URL}")

        while start_date < current_time:
            loop_counter += 1
            start_timestamp = int(start_date.timestamp())

            # Calculate potential end time
            potential_end = start_date + time_gap

            # Ensure we don't exceed current time
            if potential_end > current_time:
                end_timestamp = int(current_time.timestamp())
            else:
                end_timestamp = int(potential_end.timestamp())

            readable_start = start_date.strftime('%Y-%m-%d %H:%M:%S')

            if not cron_mode:
                print(f"Processing time window: {readable_start} to {(start_date + time_gap).strftime('%Y-%m-%d %H:%M:%S')}")

            request = json.dumps([
                "REQ",
                str(uuid.uuid4()),
                {"kinds": [0], "since": start_timestamp, "until": end_timestamp}
            ])
            ws.send(request)

            new_events_processed = False
            event_count = 0
            latest_event_timestamp = start_timestamp

            while True:
                response = ws.recv()
                data = json.loads(response)

                if data[0] == "EOSE":
                    if not cron_mode:
                        print(f"Received EOSE for window {readable_start}, events found: {event_count}")
                    break

                if data[0] == "EVENT" and "content" in data[2]:
                    event = data[2]
                    event_id = event.get("id")

                    if event_id not in processed_event_ids:
                        processed_event_ids.add(event_id)
                        content = event.get("content", "")
                        new_events_processed = True
                        event_count += 1

                        try:
                            if content:
                                content_dict = json.loads(content)
                                nip05 = content_dict.get("nip05", "")

                                if not nip05:
                                    if not cron_mode:
                                        print(f"Event {event_id} has no NIP-05 identifier")
                                    continue

                                if not is_domain_blocked(nip05, blocklist):
                                    pubkeys.add(event["pubkey"])
                                    if not cron_mode:
                                        print(f"Added pubkey {event['pubkey']} with NIP-05 {nip05}")
                                else:
                                    blocked_count += 1
                                    if not cron_mode:
                                        print(f"Blocked domain: {nip05}")

                                event_timestamp = event.get("created_at", start_timestamp)
                                latest_event_timestamp = max(latest_event_timestamp, event_timestamp)
                        except json.JSONDecodeError:
                            if not cron_mode:
                                print(f"Content is not valid JSON for event {event_id}")

            if event_count >= 500:
                # Too many events, step back
                start_date = datetime.fromtimestamp(start_timestamp) - timedelta(minutes=5)
                time_gap = timedelta(minutes=10)  # Reset to smaller gap
                growth_factor = 0
            elif event_count > 150:
                # Good number of events
                start_date = datetime.fromtimestamp(end_timestamp)
                time_gap = timedelta(minutes=20)
            elif event_count > 50:
                # Decent number of events
                start_date = datetime.fromtimestamp(end_timestamp)
                time_gap = timedelta(minutes=60)
                growth_factor += 1
            else:
                # Too few events, increase time gap exponentially but cap at 1 month
                start_date = datetime.fromtimestamp(end_timestamp)
                time_gap = min(time_gap * 2, timedelta(days=30))

            save_pubkeys_to_file(pubkeys)

            if event_count < 500:
                # Only update timestamp if we didn't get too many events
                update_last_successful_timestamp(end_timestamp)

            time_module.sleep(1)

        ws.close()
    except Exception as e:
        if not cron_mode and is_tty():
            print(f"Error fetching metadata: {e}")
            traceback.print_exc()

    duration = time_module.time() - start_time

    print(f"- Time range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"- Total profiles processed: {len(processed_event_ids)}")
    print(f"- New profiles added: {len(pubkeys)}")
    print(f"- Profiles blocked: {blocked_count}")
    print(f"- Duration: {duration:.1f} seconds")

    return pubkeys

# Save unique nhex values to the file
def save_pubkeys_to_file(pubkeys):
    existing_pubkeys = set()

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                existing_pubkeys.add(line.strip())

    all_pubkeys = existing_pubkeys.union(pubkeys)

    new_pubkeys_count = len(pubkeys - existing_pubkeys)
    pre_existing_pubkeys_count = len(existing_pubkeys)

    with open(OUTPUT_FILE, "w") as f:
        for pubkey in all_pubkeys:
            f.write(pubkey + "\n")

    if not is_tty():
        print(f"- Total profiles in database: {len(all_pubkeys)}")
        print(f"- New profiles this run: {new_pubkeys_count}")
        print(f"- Pre-existing profiles: {pre_existing_pubkeys_count}")

# Main function
def main():
    parser = argparse.ArgumentParser(description="Fetch Nostr metadata.")
    parser.add_argument('--cron', action='store_true', help="Run in cron mode (suppress progress output)")
    args = parser.parse_args()

    blocklist = load_blocklist("_unified_tier0_blocklist.csv")
    pubkeys = fetch_metadata(blocklist, args.cron)
    save_pubkeys_to_file(pubkeys)

if __name__ == "__main__":
    main()

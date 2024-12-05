import json
from datetime import datetime, timezone, timedelta
from websocket import create_connection
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse

# Relay URLs
RELAY_URL = "wss://relay.mostr.pub"
NEWS_URL = "wss://relay.nos.social"

# File paths
MATCHING_NHEX_FILE = "matching_nhex.txt"
SYNC_POSITION_FILE = "sync_position.txt"

def parse_arguments():
    parser = argparse.ArgumentParser(description="Sync events from the fediverse to nos.")
    parser.add_argument("--last-24-hours", action="store_true", help="Fetch events from the last 24 hours only.")
    return parser.parse_args()

def get_pubkeys_from_file():
    if os.path.exists(MATCHING_NHEX_FILE):
        with open(MATCHING_NHEX_FILE, "r") as file:
            return [line.strip() for line in file if line.strip()]
    return []

def get_sync_position():
    if os.path.exists(SYNC_POSITION_FILE):
        with open(SYNC_POSITION_FILE, "r") as file:
            content = file.read().strip()
            if content.isdigit():
                return int(content)
    return 0

def save_sync_position(position):
    with open(SYNC_POSITION_FILE, "w") as file:
        file.write(str(position))

def get_24_hours_ago_timestamp():
    return int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())

def fetch_and_publish_events(pubkey, line_number, last_24_hours):
    try:
        ws_fetch = create_connection(RELAY_URL)
        ws_publish = create_connection(NEWS_URL)

        # Determine the timestamp for fetching events
        since_timestamp = get_24_hours_ago_timestamp() if last_24_hours else 0
        request = json.dumps(["REQ", "unique_subscription_id", {"authors": [pubkey], "since": since_timestamp}])
        ws_fetch.send(request)
        while True:
            response = ws_fetch.recv()
            data = json.loads(response)
            if data[0] == "EOSE":  # End of subscription events
                break
            if data[0] == "EVENT":
                event = data[2]
                publish_request = json.dumps(["EVENT", {
                    "pubkey": event["pubkey"],
                    "content": event["content"],
                    "created_at": event["created_at"],
                    "id": event["id"]
                }])
                ws_publish.send(publish_request)
                publish_response = ws_publish.recv()
                publish_response_data = json.loads(publish_response)
                if publish_response_data[0] != "OK":
                    print(f"Failed to publish event ID {event['id']}.")

        ws_fetch.close()
        ws_publish.close()
    except Exception as e:
        print(f"Error fetching or publishing events for pubkey {pubkey}: {e}")

def main():
    args = parse_arguments()
    last_24_hours = args.last_24_hours

    if last_24_hours:
        print("Fetching events from the last 24 hours.")
    else:
        print("Fetching all events.")

    pubkeys = get_pubkeys_from_file()
    if not pubkeys:
        print("No pubkeys found in matching_nhex.txt.")
        return

    sync_position = get_sync_position()
    print(f"Starting sync from line {sync_position}.")

    with ThreadPoolExecutor(max_workers=100) as executor:
        progress_bar = tqdm(total=len(pubkeys) - sync_position, desc="Processing pubkeys", unit="pubkey")
        futures = {executor.submit(fetch_and_publish_events, pubkeys[i], i, last_24_hours): i for i in range(sync_position, len(pubkeys))}
        
        for future in as_completed(futures):
            line_number = futures[future]
            try:
                future.result()
                save_sync_position(line_number + 1)
                progress_bar.update(1)
            except Exception as e:
                print(f"Error processing line {line_number}: {e}")

        progress_bar.close()

        # Reset to the beginning of the list
        sync_position = 0
        save_sync_position(sync_position)
        print("Reached end of pubkey list. Restarting from the top.")

if __name__ == "__main__":
    main()

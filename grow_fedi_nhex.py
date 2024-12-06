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
import time
from datetime import datetime, timedelta
import traceback
import math
import argparse
import sys

# Configuration
RELAY_URL = "wss://relay.mostr.pub"
TARGET_IDENTIFIER = "brid.gy_at_bsky"
OUTPUT_FILE = "matching_nhex.txt"
TIMESTAMP_FILE = "last_successful_timestamp.txt"

# Load blocklist domains from the CSV file
def load_blocklist(file_path):
    blocklist = set()
    with open(file_path, newline='') as csvfile:
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
            if timestamp_str:
                return datetime.fromtimestamp(int(timestamp_str))
    return None

# Update the timestamp file with the latest successful timestamp
def update_last_successful_timestamp(timestamp):
    with open(TIMESTAMP_FILE, "w") as f:
        f.write(str(int(timestamp.timestamp())))

# Function to check if the script is running in a TTY
def is_tty():
    return sys.stdout.isatty()

# Fetch kind: 0 metadata events from the relay
def fetch_metadata(blocklist, cron_mode=False):
    pubkeys = set()
    processed_event_ids = set()
    
    # Use the last successful timestamp if available, otherwise start from May 1, 2024
    start_date = read_last_successful_timestamp() or datetime(2022, 5, 6)
    current_time = datetime.now()
    loop_counter = 0
    time_gap = timedelta(hours=1)  # Initial time gap
    growth_factor = 1  # Start with a 1-day increment

    try:
        ws = create_connection(RELAY_URL)
        
        while start_date < current_time:
            loop_counter += 1
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int((start_date + time_gap).timestamp())
            readable_start = start_date.strftime('%Y-%m-%d %H:%M:%S')
            readable_end = (start_date + time_gap).strftime('%Y-%m-%d %H:%M:%S')
            
            if not cron_mode and is_tty():
                print(f"Loop {loop_counter}: Requesting events from {readable_start}")
            
            # Subscribe to all kind: 0 events with a time filter
            request = json.dumps([
                "REQ", 
                "metadata_subscription", 
                {"kinds": [0], "since": start_timestamp, "until": end_timestamp}
            ])
            ws.send(request)
            
            new_events_processed = False
            event_count = 0  # Counter for events in this cycle
            latest_event_timestamp = start_timestamp  # Track the latest timestamp in this batch
            first_event_timestamp = None  # Initialize to track the first event's timestamp
            
            while True:
                response = ws.recv()
                data = json.loads(response)
                
                if data[0] == "EOSE":  # End of subscription events
                    if not cron_mode and is_tty():
                        print(f"Found: {event_count} profiles of {len(pubkeys)}")
                    break
                
                if data[0] == "EVENT" and "content" in data[2]:
                    event = data[2]
                    event_id = event.get("id")
                    
                    if event_id not in processed_event_ids:
                        processed_event_ids.add(event_id)
                        content = event.get("content", "")
                        new_events_processed = True
                        event_count += 1  # Increment event count
                        
                        # Capture the timestamp of the first event
                        if first_event_timestamp is None:
                            first_event_timestamp = event.get("created_at", start_timestamp)
                        
                        try:
                            if content:  # Ensure content is not None
                                content_dict = json.loads(content)
                                nip05 = content_dict.get("nip05", "")
                                
                                # Skip processing if nip05 is None or empty
                                if not nip05:
                                    continue
                                
                                if not is_domain_blocked(nip05, blocklist):
                                    pubkeys.add(event["pubkey"])
                                else:
                                    print(f"Domain blocked: {nip05}")
                                
                                # Update latest_event_timestamp to the event's timestamp
                                event_timestamp = event.get("created_at", start_timestamp)
                                latest_event_timestamp = max(latest_event_timestamp, event_timestamp)
                        except json.JSONDecodeError:
                            print("Content is not valid JSON.")
            
            # Adjust time gap based on the number of events found
            if event_count >= 500:
                # Retrace to capture missing events at the start of the range
                end_timestamp = int((datetime.fromtimestamp(start_timestamp) - timedelta(minutes=5)).timestamp())
                start_date = datetime.fromtimestamp(start_timestamp)  # Ensure start_date is reset correctly
                time_gap = timedelta(seconds=(end_timestamp - start_timestamp))  # Calculate the time gap
                growth_factor = 0  # Reset growth factor
                if not cron_mode and is_tty():
                    print(f"Retracing time gap to {time_gap}. Using first event timestamp for next range.")
            elif event_count > 150:
                # Reset the time gap to 20 minutes
                start_date = datetime.fromtimestamp(end_timestamp)  # Move to the end of the current range
                time_gap = timedelta(minutes=20)  # Set to 20 minutes
                end_timestamp = start_date + time_gap
                if not cron_mode and is_tty():
                    print(f"Resetting time gap to {time_gap}.")
            elif event_count > 50:
                # Shrink the time gap
                start_date = datetime.fromtimestamp(end_timestamp)  # Move to the end of the current range
                time_gap = timedelta(minutes=60)   # Slower growth using square root
                growth_factor += 1  # Increase the growth factor for the next cycle
                end_timestamp = start_date + time_gap
                if not cron_mode and is_tty():
                    print(f"Resetting time gap to {time_gap}.")
            else:
                # Grow the time gap when there are fewer than 50 events
                start_date = datetime.fromtimestamp(end_timestamp)  # Move to the end of the current range
                time_gap = max(timedelta(minutes=10), time_gap * 2)  # Multiply the current gap by 2
                end_timestamp = start_date + time_gap
                if not cron_mode and is_tty():
                    print(f"Increasing time gap to {time_gap}.")
            
            # Save pubkeys to file after each request cycle
            save_pubkeys_to_file(pubkeys)
            
            # Update the last successful timestamp if less than 500 events were found
            if event_count < 500:
                update_last_successful_timestamp(end_timestamp)
            
            # Optionally, add a delay to avoid overwhelming the relay
            time.sleep(1)
        
        ws.close()
    except Exception as e:
        if not cron_mode and is_tty():
            print(f"Error fetching metadata: {e}")
            traceback.print_exc()
            print(f"Current state: start_date={start_date}, current_time={current_time}, loop_counter={loop_counter}")
    
    return pubkeys

# Save unique nhex values to the file
def save_pubkeys_to_file(pubkeys):
    existing_pubkeys = set()
    
    # Load existing pubkeys from the file if it exists
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                existing_pubkeys.add(line.strip())
    
    # Combine existing pubkeys with new ones
    all_pubkeys = existing_pubkeys.union(pubkeys)
    
    # Calculate new and pre-existing counts
    new_pubkeys_count = len(pubkeys - existing_pubkeys)
    pre_existing_pubkeys_count = len(existing_pubkeys)
    
    # Write all unique pubkeys back to the file
    with open(OUTPUT_FILE, "w") as f:
        for pubkey in all_pubkeys:
            f.write(pubkey + "\n")
    
    if not is_tty():
        print(f"Public keys saved to {OUTPUT_FILE}")
        print(f"New public keys added: {new_pubkeys_count}")
        print(f"Pre-existing public keys: {pre_existing_pubkeys_count}")

# Main function
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Fetch Nostr metadata.")
    parser.add_argument('--cron', action='store_true', help="Run in cron mode (suppress progress output)")
    args = parser.parse_args()

    # Define the allowed start and end times
    allowed_start_time = time(9, 0)  # 9:00 AM
    allowed_end_time = time(17, 0)   # 5:00 PM

    # Get the current time
    current_time = datetime.now().time()

    # Check if the current time is within the allowed time range
    if allowed_start_time <= current_time <= allowed_end_time:
        blocklist = load_blocklist("_unified_tier0_blocklist.csv")
        pubkeys = fetch_metadata(blocklist, args.cron)
        save_pubkeys_to_file(pubkeys)
    else:
        if not args.cron and is_tty():
            print("The script can only run between 9:00 AM and 5:00 PM.")

if __name__ == "__main__":
    main()

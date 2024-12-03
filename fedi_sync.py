import json
from datetime import datetime
from websocket import create_connection
import requests
import os

# Relay URL and Publishers
RELAY_URL = "wss://relay.mostr.pub"
NEWS_URL = "wss://relay.nos.social"  # Corrected to the Nostr relay URL
PUBLISHERS = [

]

LAST_RUN_FILE = "last_ran_fedisync_timestamp.txt"

def get_last_run_timestamp():
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r") as file:
            return int(file.read().strip())
    return None

def save_current_timestamp():
    with open(LAST_RUN_FILE, "w") as file:
        file.write(str(int(datetime.utcnow().timestamp())))

def get_pubkeys_from_file(filename="matching_nhex.txt"):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return [line.strip() for line in file if line.strip()]
    return []

# Fetch recent events from the relay
def fetch_and_publish_events(pubkeys, since=None):
    try:
        ws_fetch = create_connection(RELAY_URL)
        ws_publish_news = create_connection(NEWS_URL)
        ws_publish_relay = create_connection(RELAY_URL)
        
        for pubkey in pubkeys:
            events = []  # Reset events for each pubkey
            # Nostr protocol request to fetch events for the pubkey
            request = {
                "authors": [pubkey]
            }
            if since is not None:
                request["since"] = since
            ws_fetch.send(json.dumps(["REQ", "unique_subscription_id", request]))
            while True:
                response = ws_fetch.recv()
                data = json.loads(response)
                if data[0] == "EOSE":  # End of subscription events
                    break
                if data[0] == "EVENT":
                    events.append(data[2])  # Append the event data
                    print(f"\r{len(events)} events fetched for {pubkey}", end='')  # Update in place
            
            # Publish events immediately after fetching for each pubkey
            if events:
                print(f"\nPublishing {len(events)} events for {pubkey} to relay.nos.social...")
                publish_to_nostr_relay(events, ws_publish_news)
        ws_fetch.close()
        ws_publish_news.close()
        ws_publish_relay.close()
    except Exception as e:
        print(f"Error fetching or publishing events: {e}")

def publish_to_nostr_relay(events, ws):
    try:
        for event in events:
            # Nostr protocol request to publish an event
            request = json.dumps(["EVENT", {
                "pubkey": event["pubkey"],
                "content": event["content"],
                "created_at": event["created_at"],
                "id": event["id"]
            }])
            ws.send(request)
            response = ws.recv()
            response_data = json.loads(response)
            if response_data[0] == "OK":
                print(f"Published event ID {event['id']} to news.nos.social successfully.")
            else:
                print(f"Failed to publish event ID {event['id']} to news.nos.social. Response: {response_data}")
    except Exception as e:
        print(f"Error publishing to news.nos.social: {e}")

def publish_to_nostr_relay(events, ws):
    try:
        for event in events:
            # Nostr protocol request to publish an event
            request = json.dumps(["EVENT", {
                "pubkey": event["pubkey"],
                "content": event["content"],
                "created_at": event["created_at"],
                "id": event["id"]
            }])
            ws.send(request)
            response = ws.recv()
            response_data = json.loads(response)
            if response_data[0] == "OK":
                print(f"Published event ID {event['id']} to Nostr relay successfully.")
            else:
                print(f"Failed to publish event ID {event['id']} to Nostr relay. Response: {response_data}")
    except Exception as e:
        print(f"Error publishing to Nostr relay: {e}")

# Main function
def main():
    pubkeys = get_pubkeys_from_file()
    if not pubkeys:
        print("No pubkeys found in matching_nhex.txt.")
        return

    last_run_timestamp = get_last_run_timestamp()
    print("Fetching and publishing recent events from Nostr relay...")
    fetch_and_publish_events(pubkeys, since=last_run_timestamp)
    save_current_timestamp()

if __name__ == "__main__":
    main()

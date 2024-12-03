import json
from datetime import datetime
from websocket import create_connection
import requests
import os

# Relay URL and Publishers
RELAY_URL = "wss://relay.mostr.pub"
NEWS_URL = "wss://news.nos.social"  # Corrected to the Nostr relay URL
PUBLISHERS = [
    "b43cdcbe1b5a991e91636c1372abd046ff1d6b55a17722a2edf2d888aeaa3150",
    "9561cd80e1207f685277c5c9716dde53499dd88c525947b1dde51374a81df0b9",
    "e526964aad10b63c24b3a582bfab4ef5937c559bfbfff3c18cb8d94909598575",
    "36de364c2ea2a77f2ed42cd7f2528ef547b6ab0062e3645046188511fe106403",
    "99d0c998eaf2dbfaead9abf50919eba6495d8d615f0ded6b320948a4a4f8c478",
    "715dc06230d7c6aa62b044a8a764728ae6862eb100f1800ef91d5cc9f972dc55",
    "e70d313e00d3d77c3ca7324c082fce9bbdefbe1b88cf39d4e48078c1573808ed",
    "0403c86a1bb4cfbc34c8a493fbd1f0d158d42dd06d03eaa3720882a066d3a378",
    "a78363acf392e7f6805d9d87654082dd83a02c6c565c804533e62b6f1da3f17d",
    "b5ad453f5410107a61fde33b0bf7f61832e96b13f8fd85474355c34818a34091",
    "2a5ce82d946a0e086f9228f68494f3597e91510c66bd201b442c968cd8381502",
    "68ac0f27c0545377ec6e7c5ce6aa2d6ef8aa1edadc6a8c2ffae8eda07f26affc",
    "407069c625e86232ae5c5709a6d2c71ef8df24f61d3c57784ca5404cb10229a0",
    "04d1fabc2623f568dc600d7ebb4ea1a13b8ccfdc2c5bca1d955f769f4562e82f",
    "d4a5cb6ef3627f22a9ac5486716b8d4dc44270898ef16da75d4ba05754cdbdc5",
    "fd615dad65d0a6ee443f4e49c0da3e26a264f42ea67d694fdceb38e7abeceb28",
    "696736ec91f9b497bf0480f73530abd5c4a3bf8e261cfb23096dd88297a2190f",
    "82acde23330b88e6831146a373eee2716c57df3e0054c5187169e92ee0880120"
]

LAST_RUN_FILE = "last_ran_timestamp.txt"

def get_last_run_timestamp():
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r") as file:
            return int(file.read().strip())
    return None

def save_current_timestamp():
    with open(LAST_RUN_FILE, "w") as file:
        file.write(str(int(datetime.utcnow().timestamp())))

# Fetch recent events from the relay
def fetch_events(pubkeys, since=None):
    events = []
    try:
        ws = create_connection(RELAY_URL)
        for pubkey in pubkeys:
            # Nostr protocol request to fetch events for the pubkey
            request = {
                "authors": [pubkey]
            }
            if since:
                request["since"] = since
            ws.send(json.dumps(["REQ", "unique_subscription_id", request]))
            while True:
                response = ws.recv()
                data = json.loads(response)
                if data[0] == "EOSE":  # End of subscription events
                    break
                if data[0] == "EVENT":
                    events.append(data[2])  # Append the event data
        ws.close()
    except Exception as e:
        print(f"Error fetching events: {e}")
    return events

# Publish events to news.nos.social
def publish_to_news(events):
    try:
        ws = create_connection(NEWS_URL)
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
        ws.close()
    except Exception as e:
        print(f"Error publishing to news.nos.social: {e}")

# Main function
def main():
    last_run_timestamp = get_last_run_timestamp()
    print("Fetching recent events from Nostr relay...")
    recent_events = fetch_events(PUBLISHERS, since=last_run_timestamp)
    if recent_events:
        print(f"Fetched {len(recent_events)} events. Publishing to news.nos.social...")
        publish_to_news(recent_events)
    else:
        print("No events found.")
    save_current_timestamp()

if __name__ == "__main__":
    main()

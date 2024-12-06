import json
from datetime import datetime, timezone
from websocket import create_connection
import os
import sys
import argparse

# Relay URL and Publishers
RELAY_URL = "wss://relay.mostr.pub"
NEWS_URL = "wss://news.nos.social"
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

LAST_RUN_FILE = "news_sync_timestamp.txt"

def parse_arguments():
    parser = argparse.ArgumentParser(description="News synchronization script.")
    parser.add_argument("--cron", action="store_true", help="Run script in cron mode, suppressing progress output.")
    return parser.parse_args()

def is_running_in_cron(cron_arg):
    return cron_arg or not sys.stdout.isatty()

def get_last_run_timestamp():
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r") as file:
            content = file.read().strip()
            if content.isdigit():
                return int(content)
            else:
                print("Warning: last_ran_timestamp.txt is empty or contains invalid data.")
    return None

def save_current_timestamp():
    try:
        with open(LAST_RUN_FILE, "w") as file:
            file.write(str(int(datetime.now(timezone.utc).timestamp())))
        print("Timestamp saved successfully.")
    except Exception as e:
        print(f"Error saving timestamp: {e}")

def fetch_events(pubkeys, since=None, cron_mode=False):
    events = []
    try:
        ws = create_connection(RELAY_URL)
        for pubkey in pubkeys:
            if not cron_mode:
                print(f"Fetching events for {pubkey}")
            request = {"authors": [pubkey]}
            if since:
                request["since"] = since
            ws.send(json.dumps(["REQ", "unique_subscription_id", request]))
            while True:
                response = ws.recv()
                data = json.loads(response)
                if data[0] == "EOSE":
                    break
                if data[0] == "EVENT":
                    events.append(data[2])
        ws.close()
    except Exception as e:
        print(f"Error fetching events: {e}")
    return events

def publish_to_news(events, cron_mode=False):
    try:
        ws = create_connection(NEWS_URL)
        for event in events:
            if not cron_mode:
                print(f"Publishing event ID {event['id']}")
            request = json.dumps(["EVENT", {
                "pubkey": event["pubkey"],
                "content": event["content"],
                "created_at": event["created_at"],
                "id": event["id"]
            }])
            ws.send(request)
            response = ws.recv()
            response_data = json.loads(response)
            if response_data[0] != "OK":
                print(f"Failed to publish event ID {event['id']}. Response: {response_data}")
        ws.close()
    except Exception as e:
        print(f"Error publishing to news.nos.social: {e}")

def main():
    args = parse_arguments()
    cron_mode = is_running_in_cron(args.cron)

    last_run_timestamp = get_last_run_timestamp()
    recent_events = fetch_events(PUBLISHERS, since=last_run_timestamp, cron_mode=cron_mode)
    save_current_timestamp()
    if recent_events:
        publish_to_news(recent_events, cron_mode=cron_mode)

if __name__ == "__main__":
    main()

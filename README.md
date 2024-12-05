# Fediverse to Nostr Synchronization

This repository contains two Python scripts designed to synchronize events between the Fediverse and Nostr platforms. The scripts are:

- `sync_fediverse_to_nos.py`
- `news_sync.py`

## Overview

### sync_fediverse_to_nos.py

This script fetches events from a Nostr relay for a list of public keys and republishes them to another Nostr relay. It uses a multi-threaded approach to handle multiple public keys concurrently, ensuring efficient processing.

#### How It Works

1. **Read Public Keys**: The script reads public keys from `matching_nhex.txt`.
2. **Fetch Events**: For each public key, it connects to a Nostr relay and fetches events.
3. **Publish Events**: The fetched events are then published to another Nostr relay.
4. **Progress Tracking**: The script uses a progress bar to show the synchronization progress.
5. **Sync Position**: It saves the last processed position to `sync_position.txt` to resume from where it left off in case of interruptions.

### news_sync.py

This script fetches recent events from a Nostr relay for a predefined list of publishers and republishes them to a news relay.

#### How It Works

1. **Fetch Events**: Connects to a Nostr relay and fetches recent events for a list of predefined publishers.
2. **Publish Events**: Publishes the fetched events to a news relay.
3. **Timestamp Management**: It saves the timestamp of the last run to `news_sync_timestamp.txt` to fetch only new events in subsequent runs.
4. **Progress Tracking**: Uses a progress bar to show the progress of fetching and publishing events.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/fediverse-nostr-sync.git
   cd fediverse-nostr-sync
   ```

2. **Create a Virtual Environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Ensure `requirements.txt` includes:
   ```
   websocket-client
   tqdm
   ```

## Running the Scripts

### sync_fediverse_to_nos.py

1. **Prepare the Public Keys**: Ensure `matching_nhex.txt` contains the public keys you want to process, one per line.

2. **Run the Script**:
   ```bash
   python sync_fediverse_to_nos.py
   ```

   The script will start processing from the last saved position in `sync_position.txt`.

### news_sync.py

1. **Run the Script**:
   ```bash
   python news_sync.py
   ```

   The script will fetch and publish events based on the last run timestamp saved in `news_sync_timestamp.txt`.

## Notes

- Ensure you have a stable internet connection as the scripts rely on WebSocket connections to Nostr relays.
- Adjust the `RELAY_URL` and `NEWS_URL` in the scripts if you need to connect to different relays.
- The scripts are designed to handle errors gracefully, but ensure your environment is set up correctly to avoid issues.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

import json
from datetime import datetime, timezone
from websocket import create_connection, WebSocket
from typing import List, Optional, Dict, Any
import os
import sys
import time

class RelaySyncer:
    def __init__(self, input_relay: str, output_relay: str, timestamp_file: Optional[str] = None, quiet_mode: bool = False):
        """
        Initialize the syncer with configuration

        Args:
            input_relay: Input relay URL to fetch from
            output_relay: Output relay URL to publish to
            timestamp_file: File to store last run timestamp
            quiet_mode: Whether to suppress progress output
        """
        self.input_relay = input_relay
        self.output_relay = output_relay
        self.timestamp_file = timestamp_file
        self.quiet_mode = quiet_mode
        self.timeout = 30  # Connection timeout in seconds

    def _log(self, message: str, end: str = '\n') -> None:
        """Internal method for logging messages"""
        print(message, end=end)

    def _debug(self, message: str, end: str = '\n') -> None:
        """Internal method for debug logging when not in quiet mode"""
        if not self.quiet_mode:
            print(message, end=end)

    def _get_last_run_timestamp(self) -> Optional[int]:
        """
        Internal method to get the timestamp of last successful run

        Returns:
            Optional[int]: Timestamp of last run or None if not available
        """
        if not self.timestamp_file or not os.path.exists(self.timestamp_file):
            return None

        try:
            with open(self.timestamp_file, "r") as file:
                content = file.read().strip()
                return int(float(content))
        except (ValueError, IOError) as e:
            self._log(f"Warning: Error reading {self.timestamp_file}: {e}")
            return None

    def _save_current_timestamp(self) -> None:
        """Internal method to save the current timestamp for future runs"""
        if not self.timestamp_file:
            return

        try:
            current_time = int(datetime.now(timezone.utc).timestamp())
            with open(self.timestamp_file, "w") as file:
                file.write(str(current_time))
        except IOError as e:
            self._log(f"Error saving timestamp: {e}")

    def _create_connection(self, url: str) -> WebSocket:
        """Internal method to create a websocket connection with timeout"""
        try:
            return create_connection(url, timeout=self.timeout)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {url}: {e}")

    def _fetch_events_for_pubkey(self, ws: WebSocket, pubkey: str, since: Optional[int]) -> List[Dict[str, Any]]:
        """
        Internal method to fetch events for a single pubkey

        Args:
            ws: WebSocket connection to fetch from
            pubkey: Public key to fetch events for
            since: Optional timestamp to fetch events since

        Returns:
            List of events
        """
        events = []
        request = {"authors": [pubkey]}
        if since is not None:
            request["since"] = since

        try:
            ws.send(json.dumps(["REQ", "unique_subscription_id", request]))
            while True:
                response = ws.recv()
                data = json.loads(response)
                if data[0] == "EOSE":
                    break
                if data[0] == "EVENT":
                    events.append(data[2])
                    self._debug(f"\r{len(events)} events fetched for {pubkey}", end='')

            if events:
                self._debug("")  # New line after progress
            return events
        except Exception as e:
            self._log(f"\nError fetching events for {pubkey}: {e}")
            return []

    def _publish_events(self, ws: WebSocket, events: List[Dict[str, Any]]) -> int:
        """
        Internal method to publish events to the output relay

        Args:
            ws: WebSocket connection to publish to
            events: List of events to publish

        Returns:
            Number of successfully published events
        """
        successful = 0
        for event in events:
            try:
                request = json.dumps(["EVENT", {
                    "pubkey": event["pubkey"],
                    "kind": event["kind"],
                    "content": event["content"],
                    "created_at": event["created_at"],
                    "tags": event["tags"],
                    "sig": event["sig"],
                    "id": event["id"]
                }])
                ws.send(request)
                response = ws.recv()
                response_data = json.loads(response)
                if response_data[0] == "OK":
                    successful += 1
                else:
                    self._log(f"Failed to publish event ID {event['id']}. Response: {response_data}")
            except Exception as e:
                self._log(f"Error publishing event {event.get('id', 'unknown')}: {e}")

        return successful

    def fetch_and_publish_events(self, pubkeys: List[str]) -> int:
        """
        Fetch events from input relay and publish to output relay.
        Uses the last run timestamp automatically if a timestamp file is configured.

        Args:
            pubkeys: List of pubkeys to fetch events for

        Returns:
            Number of successfully published events
        """
        successful_syncs = 0
        ws_fetch = None
        ws_publish = None

        try:
            self._debug(f"\nConnecting to relays...")
            ws_publish = self._create_connection(self.output_relay)
            ws_fetch = self._create_connection(self.input_relay)

            since = self._get_last_run_timestamp()

            if since:
                dt = datetime.fromtimestamp(since, timezone.utc)
                self._debug(f"Fetching events since {dt}")
            self._debug(f"Fetching from {self.input_relay}...")

            for pubkey in pubkeys:
                events = self._fetch_events_for_pubkey(ws_fetch, pubkey, since)
                if events:
                    self._debug(f"Publishing {len(events)} events for {pubkey} to {self.output_relay}...")
                    successful_syncs += self._publish_events(ws_publish, events)

                self._save_current_timestamp()

        except Exception as e:
            self._log(f"Error during sync: {e}")

        finally:
            # Ensure connections are closed
            for ws in [ws_fetch, ws_publish]:
                if ws:
                    try:
                        ws.close()
                    except:
                        pass

        return successful_syncs
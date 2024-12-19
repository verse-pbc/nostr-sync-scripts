import json
from websocket import create_connection
import os
from datetime import datetime
import time
from tqdm import tqdm
import random
import argparse

# Relay URLs (same as sync script)
RELAY_URL = "wss://relay.mostr.pub"
NEWS_URL = "wss://relay.nos.social"
MATCHING_NHEX_FILE = "matching_nhex.txt"

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Monitor nostr sync status')
    parser.add_argument('--interactive', action='store_true', 
                       help='Run in interactive mode with detailed output')
    return parser.parse_args()

def check_file_growth():
    """Monitor the growth of matching_nhex.txt"""
    if not os.path.exists(MATCHING_NHEX_FILE):
        return {"status": "error", "message": "matching_nhex.txt not found"}
    
    # Get current stats
    current_size = os.path.getsize(MATCHING_NHEX_FILE)
    with open(MATCHING_NHEX_FILE, "r") as file:
        current_count = sum(1 for _ in file)
    
    # Store stats for next comparison
    stats = {
        "timestamp": datetime.now().isoformat(),
        "size_bytes": current_size,
        "line_count": current_count
    }
    
    return stats

def verify_event_sync(pubkey):
    """Check if events from a pubkey exist on both relays"""
    results = {"source": 0, "destination": 0, "matching": 0}
    
    try:
        # Check source relay with timeout
        ws_source = create_connection(RELAY_URL, timeout=10)
        source_events = set()
        
        request = json.dumps(["REQ", "source_check", {
            "authors": [pubkey],
            "limit": 10
        }])
        ws_source.send(request)
        
        timeout = time.time() + 10  # 10 second timeout
        while time.time() < timeout:
            response = ws_source.recv()
            data = json.loads(response)
            if data[0] == "EOSE":
                break
            if data[0] == "EVENT":
                source_events.add(data[2]["id"])
        
        ws_source.close()
        results["source"] = len(source_events)
        
        # Check destination relay with timeout
        if source_events:
            ws_dest = create_connection(NEWS_URL, timeout=10)
            dest_events = set()
            
            request = json.dumps(["REQ", "dest_check", {
                "ids": list(source_events)
            }])
            ws_dest.send(request)
            
            timeout = time.time() + 10
            while time.time() < timeout:
                response = ws_dest.recv()
                data = json.loads(response)
                if data[0] == "EOSE":
                    break
                if data[0] == "EVENT":
                    dest_events.add(data[2]["id"])
            
            ws_dest.close()
            results["destination"] = len(dest_events)
            results["matching"] = len(source_events.intersection(dest_events))
            
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            if "mostr.pub" in error_msg:
                return {"error": "relay.mostr.pub offline"}
            elif "nos.social" in error_msg:
                return {"error": "relay.nos.social offline"}
        return {"error": str(e)}
    
    return results

def main():
    args = parse_arguments()
    is_interactive = args.interactive
    
    # Check file growth
    file_stats = check_file_growth()
    if is_interactive:
        print("\nFile Statistics:")
        print(f"Current size: {file_stats['size_bytes']} bytes")
        print(f"Number of pubkeys: {file_stats['line_count']}")
    
    # Sample random pubkeys for verification
    with open(MATCHING_NHEX_FILE, "r") as file:
        pubkeys = file.readlines()
    
    sample_size = min(100, len(pubkeys))
    sample_pubkeys = random.sample(pubkeys, sample_size)
    
    # Always show progress bar, but with different formats for interactive/non-interactive
    if is_interactive:
        progress_bar = tqdm(sample_pubkeys, desc="Checking pubkeys", 
                          bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')
    else:
        progress_bar = tqdm(sample_pubkeys, desc="Progress", 
                          bar_format='{percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt}')
    
    missing_events = []
    successful_checks = 0
    
    for pubkey in progress_bar:
        pubkey = pubkey.strip()
        results = verify_event_sync(pubkey)
        
        if "error" in results:
            if is_interactive:
                print(f"\nError: {results['error']}")
            else:
                print(f"ERROR:{results['error']}")
            break  # Stop checking if a relay is offline
        elif results["matching"] == results["source"]:
            successful_checks += 1
        else:
            missing_events.append({
                "pubkey": pubkey,
                "source": results["source"],
                "destination": results["destination"],
                "matching": results["matching"]
            })
    
    # Only output if there are missing events
    if missing_events:
        if is_interactive:
            print("\nMissing Events Detected:")
            for event in missing_events:
                print(f"\nPubkey: {event['pubkey'][:8]}...")
                print(f"Source events: {event['source']}")
                print(f"Destination events: {event['destination']}")
                print(f"Matching events: {event['matching']}")
            print(f"\nTotal successful checks: {successful_checks}/{sample_size}")
        else:
            # Simple output for cron jobs
            print(f"SYNC_MISSING:{len(missing_events)}/{sample_size}")

if __name__ == "__main__":
    main() 
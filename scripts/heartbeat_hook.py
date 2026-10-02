import os
import sys
import json
from datetime import datetime

USER_PROFILE = os.environ.get("USERPROFILE", os.path.expanduser("~"))
USERNAME = os.environ.get("USERNAME", os.path.basename(USER_PROFILE))
MEMORY_DIR = os.path.join(USER_PROFILE, ".gemini", "tmp", USERNAME, "memory")
BACKLOG_FILE = os.path.join(MEMORY_DIR, "active_session_backlog.md")
STATE_FILE = os.path.join(MEMORY_DIR, "heartbeat_state.json")

def main():
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        raw_input = sys.stdin.read()
        
        if raw_input and raw_input.strip():
            payload = json.loads(raw_input)
            event_name = payload.get("hook_event_name", "AfterAgent")
            cwd = payload.get("cwd", os.getcwd())
            session_id = payload.get("session_id", "unknown")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. Update machine-wide heartbeat_state.json (Cross-model state bridge)
            state = {
                "last_updated": timestamp,
                "last_actor": "gemini-cli",
                "session_id": session_id,
                "cwd": cwd,
                "event": event_name,
                "status": "active"
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
    except Exception as e:
        print(f"[MemoryForge Heartbeat Hook Notice]: {str(e)}", file=sys.stderr)

    # Crucial: Output pure JSON to stdout to adhere to Gemini CLI Hook protocol
    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()

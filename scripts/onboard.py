import os
import sys
import glob
import json
import re
import subprocess
import shutil

# Resolve profile-specific environment facts dynamically
USER_PROFILE = os.environ.get("USERPROFILE", os.path.expanduser("~"))
USERNAME = os.environ.get("USERNAME", os.path.basename(USER_PROFILE))

def get_last_history_log():
    """
    Scans the Gemini CLI global history directory for the most recently modified
    session JSON log to use as a fallback if active_handoff.md is empty.
    """
    history_root = os.path.join(USER_PROFILE, ".gemini", "history")
    if not os.path.exists(history_root):
        return None
    
    json_files = glob.glob(os.path.join(history_root, "**", "*.json"), recursive=True)
    if not json_files:
        return None
        
    json_files.sort(key=os.path.getmtime, reverse=True)
    recent_file = json_files[0]
    
    try:
        with open(recent_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if isinstance(data, list) and len(data) > 0:
            last_turns = data[-2:]  # Ingest last 2 conversation turns
            summary_blocks = []
            for i, turn in enumerate(last_turns):
                user_msg = turn.get("request", {}).get("text", "No request text")
                assistant_msg = turn.get("response", {}).get("text", "No response text")
                if len(assistant_msg) > 500:
                    assistant_msg = assistant_msg[:500] + "... [truncated]"
                summary_blocks.append(f"Turn {i+1}:\nUser: {user_msg}\nAI: {assistant_msg}\n")
            return f"Auto-extracted from last session log ({os.path.basename(recent_file)}):\n" + "\n".join(summary_blocks)
    except Exception as e:
        return f"[Fallback Error parsing history: {str(e)}]"
        
    return None

def execute_targeted_cleanup():
    """
    Cleans up abandoned UUID folders, tool output caches, and rogue diagnostic files
    to prevent workspace bloat, strictly preserving the canonical MemoryForge directory.
    """
    tmp_root = os.path.join(USER_PROFILE, ".gemini", "tmp", USERNAME)
    cleaned_count = 0

    # Ensure canonical MemoryForge directory exists
    memory_dir = os.path.join(tmp_root, "memory")
    os.makedirs(memory_dir, exist_ok=True)

    # 1. Clean accidental .gemini/tmp directories inside workspace_root
    workspace_tmp = os.path.join(USER_PROFILE, "workspace_root", ".gemini", "tmp")
    if os.path.exists(workspace_tmp):
        try:
            shutil.rmtree(workspace_tmp)
            cleaned_count += 1
        except Exception:
            pass

    if not os.path.exists(tmp_root):
        return cleaned_count

    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
    
    for item in os.listdir(tmp_root):
        item_path = os.path.join(tmp_root, item)
        
        # 2. Clean abandoned UUID folders
        if os.path.isdir(item_path) and uuid_pattern.match(item):
            try:
                shutil.rmtree(item_path)
                cleaned_count += 1
            except Exception:
                pass
                
        # 3. Clean temporary chats and tool-outputs directories
        elif os.path.isdir(item_path) and item in ["chats", "tool-outputs"]:
            try:
                shutil.rmtree(item_path)
                cleaned_count += 1
            except Exception:
                pass
                
        # 4. Clean rogue or unnested handoffs and local troubleshooting artifacts
        elif os.path.isfile(item_path) and item in ["inspect_auth_output.txt", "inspect_auth.ps1", "move-acli.ps1", "handoff.md"]:
            try:
                os.remove(item_path)
                cleaned_count += 1
            except Exception:
                pass
                
    return cleaned_count

def run_workspace_validation():
    """
    Executes the workspace validator script using standard Windows PowerShell,
    returning the console output and success status.
    """
    validator_path = os.path.join(USER_PROFILE, "workspace_root", "scripts", "validate-workspace.ps1")
    if not os.path.exists(validator_path):
        return "ERROR: validate-workspace.ps1 script not found!", False
        
    try:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", validator_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        return result.stdout, (result.returncode == 0)
    except Exception as e:
        return f"ERROR running validator script: {str(e)}", False

def main():
    print("=== [HOST TOOLING] Personal Workspace Onboarder ===", file=sys.stderr)
    
    # Canonical MemoryForge storage locations (Single source of truth)
    memory_root = os.path.join(USER_PROFILE, ".gemini", "tmp", USERNAME, "memory")
    local_handoff = os.path.join(memory_root, "active_handoff.md")
    backlog_handoff = os.path.join(memory_root, "active_session_backlog.md")
    
    global_rules_path = os.path.join(USER_PROFILE, ".gemini", ".rules", "rules.md")
    workspace_rules_path = os.path.join(USER_PROFILE, "workspace_root", ".gemini", ".rules", "rules.md")
    
    # 1. Read Active Handoff Cache (Exclusively from MemoryForge)
    handoff_data = ""
    is_handoff_loaded = False
    
    try:
        if os.path.exists(local_handoff):
            with open(local_handoff, "r", encoding="utf-8") as f:
                handoff_data = f.read().strip()
            if handoff_data:
                print(f"[ONBOARD] Ingesting MemoryForge active handoff ({local_handoff})...", file=sys.stderr)
                is_handoff_loaded = True
    except Exception as e:
        print(f"[ONBOARD] ERROR reading local handoff: {str(e)}", file=sys.stderr)

    # Ingest Rolling Milestone Heartbeat with Automated Backlog Archival Rotation
    backlog_entries = []
    archive_handoff = os.path.join(memory_root, "active_session_backlog.archive.md")
    try:
        if os.path.exists(backlog_handoff):
            with open(backlog_handoff, "r", encoding="utf-8") as f:
                raw_lines = [line.strip() for line in f if line.strip().startswith("- ")]
            
            # Backlog Archival Rotation: If > 100 entries, archive older entries to keep active backlog lean
            if len(raw_lines) > 100:
                archive_count = len(raw_lines) - 50
                to_archive = raw_lines[:archive_count]
                to_keep = raw_lines[archive_count:]
                
                with open(archive_handoff, "a", encoding="utf-8") as f_arch:
                    f_arch.write("\n".join(to_archive) + "\n")
                
                with open(backlog_handoff, "w", encoding="utf-8") as f_backlog:
                    f_backlog.write("\n".join(to_keep) + "\n")
                
                print(f"[ONBOARD] MemoryForge Rotation: Archived {archive_count} historical milestones to active_session_backlog.archive.md", file=sys.stderr)
                raw_lines = to_keep

            if raw_lines:
                print(f"[ONBOARD] Ingesting MemoryForge heartbeat milestones ({len(raw_lines)} total recorded)...", file=sys.stderr)
                # Take the most recent 10 milestones to maintain high signal-to-noise ratio
                recent_milestones = raw_lines[-10:] if len(raw_lines) > 10 else raw_lines
                backlog_entries = recent_milestones
    except Exception as e:
        print(f"[ONBOARD] Warning reading heartbeat backlog: {str(e)}", file=sys.stderr)

    if backlog_entries:
        backlog_text = "\n".join(backlog_entries)
        if is_handoff_loaded:
            handoff_data += f"\n\n### 🕒 Recent Progress Heartbeat (Latest Milestones from MemoryForge):\n{backlog_text}"
        else:
            handoff_data = f"### 🕒 Recovered Progress Heartbeat (MemoryForge):\n{backlog_text}"

    # 2. Automated History Fallback (If no handoff or backlog found)
    if not is_handoff_loaded and not backlog_entries:
        print("[ONBOARD] No handoff or heartbeat found. Scanning global history logs...", file=sys.stderr)
        history_summary = get_last_history_log()
        if history_summary:
            print("[ONBOARD] SUCCESS: Context recovered from last history session!", file=sys.stderr)
            handoff_data = history_summary
        else:
            print("[ONBOARD] No history logs found. Fresh workspace setup.", file=sys.stderr)
            handoff_data = "No previous context recorded. Starting a clean, fresh session."

    # 3. Read Invariant Hard Rules (Global and Workspace)
    global_rules_data = ""
    try:
        if os.path.exists(global_rules_path):
            with open(global_rules_path, "r", encoding="utf-8") as f:
                global_rules_data = f.read().strip()
            print("[ONBOARD] Ingesting Tier 1 Global Hard Guardrails...", file=sys.stderr)
    except Exception as e:
        print(f"[ONBOARD] ERROR reading global rules: {str(e)}", file=sys.stderr)

    workspace_rules_data = ""
    try:
        if os.path.exists(workspace_rules_path):
            with open(workspace_rules_path, "r", encoding="utf-8") as f:
                workspace_rules_data = f.read().strip()
            print("[ONBOARD] Ingesting Tier 2 Pod Architecture Rules...", file=sys.stderr)
    except Exception as e:
        print(f"[ONBOARD] ERROR reading workspace rules: {str(e)}", file=sys.stderr)

    # 4. Executing Cleanup
    print("[ONBOARD] Executing targeted .gemini temporary cleanup...", file=sys.stderr)
    cleaned_dirs = execute_targeted_cleanup()
    print(f"[ONBOARD] Cleanup completed. Cleared {cleaned_dirs} abandoned folders/files.", file=sys.stderr)

    # 5. Execute Workspace Environment Validation for Daily Assurance
    print("[ONBOARD] Running daily environment verification audit...", file=sys.stderr)
    validation_output, is_valid = run_workspace_validation()
    validation_status = "[PASS] Workspace environment is 100% healthy!" if is_valid else "[FAIL] Workspace has broken links or configuration imports!"
    print(f"[ONBOARD] Validation finished with status: {validation_status}", file=sys.stderr)

    # Output consolidated onboarding payload
    onboarding_context = f"""
[SYSTEM ONBOARDING RESTORED]

### 1. Active Session Progress (Context Recovered)
{handoff_data}

### 2. Daily Environment Verification Status (Confidence Check)
Status: {validation_status}

--- DETAILS ---
{validation_output}
---------------

### 3. Tier 1 Global Workstation & Shell Guardrails (Mandatory)
{global_rules_data if global_rules_data else "No Tier 1 Global Rules found."}

### 4. Tier 2 Pod Architecture Rules (Mandatory)
{workspace_rules_data if workspace_rules_data else "No Tier 2 Pod Rules found."}

Directive: Welcome Mike back, report on the validation audit status, summarize the restored state, and await instructions.
"""
    print(onboarding_context)

if __name__ == "__main__":
    main()

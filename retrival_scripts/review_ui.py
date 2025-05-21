import streamlit as st
import json
import os
from datetime import datetime

LOGS_DIR = "logs"
AUTO_SCORE_THRESHOLD = 6

def load_logs():
    logs = []
    for fname in os.listdir(LOGS_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(LOGS_DIR, fname), "r", encoding="utf-8") as f:
                try:
                    logs.extend(json.load(f))
                except Exception:
                    continue
    return logs

def save_log_entry(entry, sender):
    log_file = os.path.join(LOGS_DIR, f"{sender}_chat_history.json")
    # Load all entries for this sender
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []
    # Find and update the entry by timestamp
    for i, e in enumerate(data):
        if e["timestamp"] == entry["timestamp"]:
            data[i] = entry
            break
    else:
        data.append(entry)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

st.title("Grace Human Review Inbox")

logs = load_logs()
flagged = [
    e for e in logs
    if (e.get("auto_score") is not None and e["auto_score"] < AUTO_SCORE_THRESHOLD)
    or e.get("human_score") is None
]

if not flagged:
    st.success("No flagged or unreviewed conversations!")
else:
    for entry in flagged:
        st.markdown("---")
        st.write(f"**Time:** {entry['timestamp']}")
        st.write(f"**Sender:** {entry['sender']}")
        st.write(f"**User:** {entry['user_message']}")
        st.write(f"**Bot:**")
        edited_reply = st.text_area(
            f"Edit reply for {entry['timestamp']}", entry["bot_reply"], key=entry["timestamp"]
        )
        st.write(f"**Auto Score:** {entry.get('auto_score')}")
        st.write(f"**State ID:** {entry.get('state_id')}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍 Approve", key="up_"+entry["timestamp"]):
                entry["human_score"] = 10
                entry["bot_reply"] = edited_reply
                save_log_entry(entry, entry["sender"])
                st.success("Approved!")
        with col2:
            if st.button("👎 Reject", key="down_"+entry["timestamp"]):
                entry["human_score"] = 1
                entry["bot_reply"] = edited_reply
                save_log_entry(entry, entry["sender"])
                st.warning("Rejected!")

        st.write("------")
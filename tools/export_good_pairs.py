import os
import json

LOGS_DIR = "logs"
EXPORT_FILE = "good_pairs.jsonl"
MIN_HUMAN_SCORE = 8

with open(EXPORT_FILE, "w", encoding="utf-8") as out:
    for fname in os.listdir(LOGS_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(LOGS_DIR, fname), "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except Exception:
                    continue
            for entry in logs:
                if entry.get("human_score", 0) >= MIN_HUMAN_SCORE:
                    out.write(json.dumps({
                        "user": entry["user_message"],
                        "reply": entry["bot_reply"]
                    }) + "\n")
print(f"Exported good pairs to {EXPORT_FILE}")

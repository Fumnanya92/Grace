import json
import re

SOURCE = "atuche_pairs.jsonl"
DEST = "good_pairs.jsonl"
MIN_LEN = 6  # Minimum length for user/reply to be considered high-quality
SCORE_THRESHOLD = 1  # Only pairs with score >= this will be merged

def is_artifact(text):
    # Add more patterns as needscore pairs before merging into good_pairs.jsonled
    patterns = [
        r"sent an attachment",
        r"liked a message",
        r"audio call",
        r"video call",
        r"missed call",
        r"sent a photo",
        r"sent a sticker",
        r"sent a file",
        r"sent a video",
        r"sent a voice message",
        r"sent a gif",
        r"sent a link",
        r"sent a location",
        r"sent a contact",
        r"sent a document",
        r"sent a payment",
        r"sent a reaction",
        r"removed a message",
        r"changed the group photo",
        r"changed the group name",
        r"added",
        r"left the group",
        r"joined the group",
        r"created the group",
    ]
    return any(re.search(pat, text.lower()) for pat in patterns)

def score_pair(user, reply):
    # Simple scoring: +1 for each side being "long enough" and not an artifact
    score = 0
    if user and len(user.strip()) >= MIN_LEN and not is_artifact(user):
        score += 1
    if reply and len(reply.strip()) >= MIN_LEN and not is_artifact(reply):
        score += 1
    return score

# Load existing good pairs (if any)
existing = set()
try:
    with open(DEST, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            existing.add(obj.get("hash") or (obj["user"] + obj["reply"]))
except FileNotFoundError:
    pass

added = 0
with open(SOURCE, "r", encoding="utf-8") as src, open(DEST, "a", encoding="utf-8") as out:
    for line in src:
        obj = json.loads(line)
        user, reply = obj["user"], obj["reply"]
        pair_hash = obj.get("hash") or (user + reply)
        if pair_hash in existing:
            continue
        score = score_pair(user, reply)
        if score >= SCORE_THRESHOLD:
            out.write(json.dumps({"user": user, "reply": reply, "hash": pair_hash}) + "\n")
            added += 1
            existing.add(pair_hash)

print(f"✅ Added {added} high-quality pairs to {DEST}")

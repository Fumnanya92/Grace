import json

INPUT = "good_pairs.jsonl"
OUTPUT = "good_pairs.cleaned.jsonl"
MIN_LEN = 3

cleaned = 0
total = 0

with open(INPUT, "r", encoding="utf-8") as fin, open(OUTPUT, "w", encoding="utf-8") as fout:
    for line in fin:
        total += 1
        try:
            obj = json.loads(line)
            user = obj.get("user", "")
            reply = obj.get("reply", "")
            if not isinstance(user, str) or not isinstance(reply, str):
                continue
            if len(user.strip()) < MIN_LEN or len(reply.strip()) < MIN_LEN:
                continue
            fout.write(json.dumps({"user": user.strip(), "reply": reply.strip()}) + "\n")
            cleaned += 1
        except Exception:
            continue

print(f"✅ Cleaned {cleaned} of {total} pairs. Output: {OUTPUT}")
#!/usr/bin/env python3
import sys, json, glob, argparse, hashlib, os

def iter_pairs(messages, agent):
    messages.sort(key=lambda m: m.get("timestamp_ms", 0))
    pending_user = None
    for m in messages:
        text = (m.get("content") or "").strip()
        if not text:
            continue
        if m["sender_name"] == agent:
            if pending_user:
                yield pending_user, text
                pending_user = None
        else:
            pending_user = text

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inbox", required=True, help="Path to inbox root (e.g. inbox/)")
    p.add_argument("--agent", required=True, help="Name of business sender (e.g. ATUCHE)")
    p.add_argument("--out", default="atuche_pairs.jsonl", help="Output JSONL path")
    args = p.parse_args()

    out = open(args.out, "w", encoding="utf-8")
    total = 0
    for root, dirs, files in os.walk(args.inbox):
        for fname in files:
            if fname.endswith(".json"):
                fpath = os.path.join(root, fname)
                try:
                    data = json.load(open(fpath, encoding="utf-8"))
                except Exception:
                    continue
                messages = data.get("messages") or data
                for u, r in iter_pairs(messages, args.agent):
                    j = {
                        "user": u,
                        "reply": r,
                        "hash": hashlib.sha1((u+r).encode()).hexdigest()
                    }
                    out.write(json.dumps(j, ensure_ascii=False) + "\n")
                    total += 1
    out.close()
    print(f"✅  Wrote {total} pairs to {args.out}")

if __name__ == "__main__":
    main()

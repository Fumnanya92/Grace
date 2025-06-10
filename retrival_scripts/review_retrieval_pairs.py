import streamlit as st
import json
import os

RETRIEVAL_FILE = "retrieval_pairs.json"
REVIEWED_FILE = "retrieval_pairs_reviewed.json"

# Load pairs
if os.path.exists(RETRIEVAL_FILE):
    with open(RETRIEVAL_FILE, "r", encoding="utf-8") as f:
        pairs = json.load(f)
else:
    st.error(f"{RETRIEVAL_FILE} not found!")
    st.stop()

# Load reviewed pairs if exists
if os.path.exists(REVIEWED_FILE):
    with open(REVIEWED_FILE, "r", encoding="utf-8") as f:
        reviewed = json.load(f)
    reviewed_hashes = {json.dumps(pair, sort_keys=True) for pair in reviewed}
else:
    reviewed = []
    reviewed_hashes = set()

st.title("Grace Retrieval Pairs Review")

for idx, pair in enumerate(pairs):
    pair_hash = json.dumps(pair, sort_keys=True)
    if pair_hash in reviewed_hashes:
        continue  # Already reviewed

    st.markdown("---")
    st.write(f"**User:** {pair['user']}")
    edited_reply = st.text_area("Edit reply", pair["reply"], key=f"reply_{idx}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 Approve", key=f"approve_{idx}"):
            reviewed.append({"user": pair["user"], "reply": edited_reply})
            with open(REVIEWED_FILE, "w", encoding="utf-8") as f:
                json.dump(reviewed, f, ensure_ascii=False, indent=2)
            st.success("Approved and saved!")
            st.rerun()
    with col2:
        if st.button("👎 Reject", key=f"reject_{idx}"):
            # Just skip adding to reviewed
            with open(REVIEWED_FILE, "w", encoding="utf-8") as f:
                json.dump(reviewed, f, ensure_ascii=False, indent=2)
            st.warning("Rejected and skipped!")
            st.rerun()

st.success("Review complete! All pairs processed.")

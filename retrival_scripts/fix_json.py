import json

with open('retrieval_pairs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)  # This will raise an error if the JSON is invalid

with open('retrieval_pairs_fixed.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("File validated and pretty-printed as retrieval_pairs_fixed.json")

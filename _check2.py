import json

with open("knowledge_base/guides/guide_cards.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 模拟 load_guide_cards 的逻辑
cards = data.get("cards", []) if isinstance(data, dict) else data
result = {}
for card in cards:
    cp_id = str(card.get("checkpoint_id") or "").strip()
    if cp_id:
        result[cp_id] = card

print("Type:", type(result))
print("Keys:", list(result.keys()))
print()
cp01 = result.get("cp_01")
if cp01:
    print("cp_01 has substeps:", len(cp01.get("substeps", [])))
    for sub in cp01.get("substeps", []):
        print(f"  - {sub.get('label')}: {len(sub.get('images', []))} images")
        for img in sub.get("images", []):
            print(f"    -> {img}")
else:
    print("cp_01 not found")

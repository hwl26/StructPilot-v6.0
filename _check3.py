import json

with open("knowledge_base/guides/guide_cards.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 模拟 load_guide_cards 返回结构
result = {}
for card in data.get("cards", []):
    cp_id = str(card.get("checkpoint_id") or "").strip()
    if cp_id:
        result[cp_id] = card

# 看 cp_01 真实结构
cp01 = result.get("cp_01", {})
print("cp_01 keys:", list(cp01.keys()))
print()
print("image_refs field type:", type(cp01.get("image_refs")))
print("image_refs value:", cp01.get("image_refs"))
print()

# substep[0]
subs = cp01.get("substeps", [])
if subs:
    sub = subs[0]
    print(f"substep[0] keys: {list(sub.keys())}")
    print(f"substep[0].images: {sub.get('images')}")

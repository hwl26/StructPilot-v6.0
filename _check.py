import sys, os, json
sys.path.insert(0, '.')

# 1. 加载 guide_cards
with open("knowledge_base/guides/guide_cards.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print("guide_cards top keys:", list(data.keys()))
cards = data.get("cards", [])
print(f"Total cards: {len(cards)}")
print()
for card in cards:
    cp_id = card.get("checkpoint_id")
    if cp_id != "cp_01":
        continue
    print(f"=== {cp_id} ===")
    print(f"image_refs: {card.get('image_refs', [])}")
    for i, sub in enumerate(card.get("substeps", [])):
        print(f"  substep[{i}].images: {sub.get('images', [])}")
    break

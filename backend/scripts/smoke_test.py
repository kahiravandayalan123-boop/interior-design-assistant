"""End-to-end smoke test against a running server.

    python scripts/smoke_test.py               # hits http://127.0.0.1:8000
    python scripts/smoke_test.py http://host:port

Exercises the happy path (upload -> chat -> generate -> products/match) plus
the error-handling paths (corrupt upload, bad style, unknown session, empty
answers) and prints a PASS/FAIL summary at the end.
"""
import struct
import sys
import zlib

import httpx2 as httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def _make_png(size: int = 48) -> bytes:
    """A real (if noisy) PNG well over the backend's minimum upload size — a
    solid color compresses away to almost nothing, so vary each pixel."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(bytes([(x * 7 + y * 13) % 256, (x * 31 + 40) % 256, (y * 17 + 80) % 256]))
    idat = zlib.compress(bytes(raw), 6)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


PNG = _make_png()

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"{'OK  ' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not cond else ""))


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=60)

    cfg = c.get("/api/config").json()
    print(f"config: anthropic_ready={cfg['anthropic_ready']} openai_ready={cfg['openai_ready']} "
          f"using_mock={cfg['using_mock']}\n")

    # ---- error paths ----------------------------------------------------
    r = c.post("/api/upload", data={"style": "Modern"}, files={"image": ("x.png", b"not a real image" * 10, "image/png")})
    check("corrupt image -> 415", r.status_code == 415, f"got {r.status_code}: {r.text[:120]}")

    r = c.post("/api/upload", data={"style": "Modern"}, files={"image": ("x.png", b"", "image/png")})
    check("empty file -> 422", r.status_code == 422, f"got {r.status_code}")

    r = c.post("/api/upload", data={"style": "Baroque"}, files={"image": ("room.png", PNG, "image/png")})
    check("invalid style -> 422", r.status_code == 422, f"got {r.status_code}")

    r = c.post("/api/chat", json={"session_id": "does-not-exist", "answers": []})
    check("unknown session on /chat -> 404", r.status_code == 404, f"got {r.status_code}")

    r = c.post("/api/generate", json={"session_id": "does-not-exist"})
    check("unknown session on /generate -> 404", r.status_code == 404, f"got {r.status_code}")

    r = c.post("/api/upload", data={}, files={"image": ("room.png", PNG, "image/png")})
    check("missing style field -> 4xx", 400 <= r.status_code < 500, f"got {r.status_code}")

    # ---- happy path -------------------------------------------------------
    r = c.post("/api/upload", data={"style": "Scandinavian"}, files={"image": ("room.png", PNG, "image/png")})
    check("upload -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    up = r.json()
    sid = up["session_id"]
    print(f"\n  session={sid} mock={up['mock']} warnings={up['warnings']}")
    print(f"  analysis.summary: {up['analysis']['summary'][:90]}...")
    print(f"  questions: {[q['id'] for q in up['questions']]}")
    for q in up["questions"]:
        print(f"    - [{q['kind']}{'*' if not q.get('optional') else ' optional'}] {q['prompt']}")
    check("2-4 questions returned", 2 <= len(up["questions"]) <= 4, str(len(up["questions"])))
    check("first question is budget", up["questions"][0]["kind"] == "budget")

    # generate before answering required questions -> 409
    r = c.post("/api/generate", json={"session_id": sid})
    check("generate before answers -> 409", r.status_code == 409, f"got {r.status_code}")

    # answer with one blank (should be dropped) + real answers
    answers = [{"question_id": "bogus-id", "answer": "ignored"}]
    for q in up["questions"]:
        pick = q["options"][0] if q.get("options") else "sample answer"
        answers.append({"question_id": q["id"], "answer": pick})
    r = c.post("/api/chat", json={"session_id": sid, "answers": answers})
    check("chat -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    chat = r.json()
    print(f"\n  chat.ready_to_generate={chat['ready_to_generate']}  reply={chat['reply']!r}")
    check("ready_to_generate after answering", chat["ready_to_generate"])
    check("recap has an entry per answered question", len(chat["answered"]) >= len(up["questions"]) - 1)

    r = c.post("/api/generate", json={"session_id": sid})
    check("generate -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    gen = r.json()
    budget_amount = float(answers_map_budget := next(a["answer"] for a in answers if a["question_id"] == "budget").replace("₹", "").replace(",", ""))
    print(f"\n  image_prompt: {gen['image_prompt'][:110]}...")
    print(f"  generated_image_url: {gen['generated_image_url']}")
    print(f"  image_is_mock={gen['image_is_mock']}  mock={gen['mock']}  warnings={gen['warnings']}")
    print(f"  planned_furniture: {[f['category'] for f in gen['planned_furniture']]}")
    print(f"  budget: {answers_map_budget}  estimated_total: {gen['estimated_total']}  product_matches_note: {gen['product_matches_note']!r}")
    print("  product_matches:")
    for m in gen["product_matches"]:
        print(f"    - {m['item']:<24} -> {m['title']} (₹{m['price']}, {m['retailer']})")
    print(f"  recommendations_total: {gen['recommendations_total']}  recommendations_note: {gen['recommendations_note']!r}")
    print("  recommendations (semantic):")
    for rec in gen["recommendations"]:
        print(f"    - [{rec['score']}] {rec['category']:<14} {rec['name']} (₹{rec['price']})")
    check("planned_furniture has >=6 items", len(gen["planned_furniture"]) >= 6, str(len(gen["planned_furniture"])))
    check("product_matches non-empty", len(gen["product_matches"]) > 0)
    check("product_matches total respects the stated budget",
          gen["estimated_total"] <= budget_amount, f"total={gen['estimated_total']} budget={budget_amount}")
    check("product_matches_note set when budget didn't cover every planned item",
          bool(gen["product_matches_note"]) == (len(gen["product_matches"]) < len(gen["planned_furniture"])),
          f"note={gen['product_matches_note']!r} matches={len(gen['product_matches'])}/{len(gen['planned_furniture'])}")
    check("recommendations non-empty", len(gen["recommendations"]) > 0, str(gen["recommendations"]))
    check("recommendations have product urls", all(r["url"] for r in gen["recommendations"]))
    check("recommendations total respects the stated budget",
          gen["recommendations_total"] <= budget_amount, f"total={gen['recommendations_total']} budget={budget_amount}")
    check("recap present", len(gen["recap"]) >= 2, str(len(gen["recap"])))

    # generated image must be same-origin and actually fetchable (download button)
    img_url = gen["generated_image_url"]
    check("generated image URL is same-origin (/media/...)", img_url.startswith(BASE + "/media/"), img_url)
    r_img = c.get(img_url)
    check("generated image is fetchable", r_img.status_code == 200 and len(r_img.content) > 500,
          f"status={r_img.status_code} bytes={len(r_img.content)}")
    check("generated image is a real PNG/JPEG", r_img.content[:8].startswith(b"\x89PNG") or r_img.content[:3] == b"\xff\xd8\xff")

    # direct product match endpoint
    r = c.post(
        "/api/products/match",
        json={"items": [{"name": "old couch", "category": "couch", "color": "grey"},
                         {"name": "reading nook chair", "category": "recliner"}],
              "style": "Modern", "budget": "₹20,000"},
    )
    check("/products/match -> 200", r.status_code == 200)
    pm = r.json()
    pm_total = sum(m["price"] for m in pm["matches"])
    print(f"\n  /products/match (budget ₹20,000): {len(pm['matches'])} item(s), total ₹{pm_total}, note={pm['note']!r}")
    check("/products/match resolves synonyms (couch, recliner)", len(pm["matches"]) > 0, str(pm["matches"]))
    check("/products/match prices are in INR", all(m["currency"] == "INR" for m in pm["matches"]), str(pm["matches"]))
    check("/products/match total respects the ₹20,000 budget", pm_total <= 20000, f"total={pm_total}")

    # ---- "Modify Existing Room" flow --------------------------------------
    r = c.post(
        "/api/modify",
        data={"instruction": "Move the coffee table closer to the window and add a reading lamp", "budget": "₹20,000"},
        files={"image": ("room.png", PNG, "image/png")},
    )
    check("modify -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    mod = r.json()
    print(f"\n  [modify] image_prompt: {mod['image_prompt'][:110]}...")
    print(f"  [modify] recap: {[(x['question'], x['answer']) for x in mod['recap']]}")
    print(f"  [modify] estimated_total: ₹{mod['estimated_total']}")
    check("modify recap includes the instruction", any(x["id"] == "instruction" for x in mod["recap"]))
    check("modify recap includes the budget", any(x["id"] == "budget" and x["answer"] == "₹20,000" for x in mod["recap"]))
    check("modify returns the original photo URL", mod["original_image_url"].startswith(BASE + "/media/"), mod["original_image_url"])
    check("modify product prices are in INR", all(m["currency"] == "INR" for m in mod["product_matches"]))
    check("modify recommendations non-empty", len(mod["recommendations"]) > 0, str(mod["recommendations"]))
    print(f"  [modify] product_matches total ₹{mod['estimated_total']} (note={mod['product_matches_note']!r}), "
          f"recommendations total ₹{mod['recommendations_total']} (note={mod['recommendations_note']!r})")
    check("modify product_matches total respects the ₹20,000 budget", mod["estimated_total"] <= 20000, str(mod["estimated_total"]))
    check("modify recommendations total respects the ₹20,000 budget", mod["recommendations_total"] <= 20000, str(mod["recommendations_total"]))

    r = c.post(
        "/api/modify",
        data={"instruction": "", "budget": "₹20,000"},
        files={"image": ("room.png", PNG, "image/png")},
    )
    check("modify with blank instruction -> 422", r.status_code == 422, f"got {r.status_code}")

    r = c.post(
        "/api/modify",
        data={"instruction": "make it nicer", "budget": "$500"},
        files={"image": ("room.png", PNG, "image/png")},
    )
    check("modify with invalid budget -> 422", r.status_code == 422, f"got {r.status_code}")

    # ---- summary ------------------------------------------------------
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("ALL GOOD.")


if __name__ == "__main__":
    main()

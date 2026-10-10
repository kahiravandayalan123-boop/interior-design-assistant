"""Run both user flows against a server and check the things that matter.

    python scripts/flow_check.py                      # http://127.0.0.1:8000
    python scripts/flow_check.py https://host [photo] [room_size] [outdir]

Prints timings, the keep/replace verdicts, the plan, the structure check and
every shopping link, then a PASS/FAIL list. With `outdir` it also saves the
before/after images for a visual look. Real keys => real provider calls.
"""
import json
import sys
import time
from pathlib import Path

import httpx2 as httpx

sys.stdout.reconfigure(encoding="utf-8")
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PHOTO = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parents[2] / "frontend/public/samples/sunny-living-room.jpg")
ROOM_SIZE = sys.argv[3] if len(sys.argv) > 3 else ""
OUT = Path(sys.argv[4]) if len(sys.argv) > 4 else None
ORIGIN = "https://interior-design-assistant-omega.vercel.app"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def timed(label, fn):
    start = time.time()
    r = fn()
    print(f"\n[{label}] HTTP {r.status_code} in {time.time() - start:.1f}s")
    if r.status_code != 200:
        print("   ", r.text[:400])
    return r


def show_result(tag, r):
    d = r.json()
    print("  plan:")
    for p in d["planned_furniture"]:
        print(f"    {p['action'] or '?':8} {p['name']} [{p['category']}] {p['size']} — {p['reason']}")
    print("  image_prompt:", d["image_prompt"])
    print("  structure_check:", d["structure_check"], "| warnings:", d["warnings"])
    print(f"  shopping (₹{d['estimated_total']:.0f}) + extras (₹{d['recommendations_total']:.0f}):")
    links = []
    for m in d["product_matches"]:
        print(f"    {m['action']:8} {m['item']} -> {m['title']} ₹{m['price']:.0f}")
        links += [l["url"] for l in m["shop_links"]]
    for m in d["recommendations"]:
        print(f"    extra    {m['name']} [{m['category']}] ₹{m['price']:.0f}")
        links += [l["url"] for l in m["shop_links"]]

    check(f"{tag}: not sample data", not d["mock"] or "127.0.0.1" in BASE or "localhost" in BASE)
    check(f"{tag}: architecture preserved", d["structure_check"]["status"] in ("passed", "corrected", "skipped"),
          d["structure_check"]["status"])
    actions = {p["action"] for p in d["planned_furniture"]}
    check(f"{tag}: every planned piece has a keep/replace/remove/add verdict", "" not in actions, str(actions))
    bought = {m["item"] for m in d["product_matches"]}
    kept = {p["name"] for p in d["planned_furniture"] if p["action"] in ("keep", "remove")}
    check(f"{tag}: shopping list has no kept/removed pieces", not (bought & kept), str(bought & kept))
    kept_cats = {p["category"] for p in d["planned_furniture"]}
    check(f"{tag}: extras avoid categories already in the plan",
          not any(m["category"] in kept_cats for m in d["recommendations"]))
    check(f"{tag}: no placeholder links", links == [] or not any("example.com" in u for u in links), f"{len(links)} links")
    all_urls = json.dumps(d)
    check(f"{tag}: no example.com anywhere in response", "example.com" not in all_urls)
    return d, links


def main():
    c = httpx.Client(base_url=BASE, timeout=400)
    h = c.get("/health").json()
    cfg = c.get("/api/config").json()
    print("health:", h, "\nconfig:", cfg)

    pre = c.options("/api/generate", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "content-type"})
    check("CORS preflight from the production site", pre.status_code == 200
          and pre.headers.get("access-control-allow-origin") == ORIGIN, f"{pre.status_code}")

    photo = PHOTO.read_bytes()
    files = lambda: {"image": (PHOTO.name, photo, "image/jpeg")}  # noqa: E731

    # ---- New Room Design -------------------------------------------------
    r = timed("upload", lambda: c.post("/api/upload", data={"style": "Modern", "room_size": ROOM_SIZE}, files=files()))
    check("upload ok", r.status_code == 200)
    if r.status_code != 200:
        return
    u = r.json()
    a = u["analysis"]
    print(f"  {a['room_type']} | {a['size_class']} | {a['size_estimate']} (from user: {a['size_from_user']})")
    print("  structure:", json.dumps(a["structure"], ensure_ascii=False))
    for f in a["existing_furniture"]:
        print(f"    {f['action'] or '?':8} {f['name']} {f['size']} — {f['reason']}")
    check("every existing piece has a verdict and a reason",
          all(f["action"] in ("keep", "replace", "remove") and f["reason"] for f in a["existing_furniture"]))
    ids = [q["id"] for q in u["questions"]]
    print("  questions:", [(q["prompt"], q["options"]) for q in u["questions"]])
    check("questions are the fixed clean set", ids == ["budget", "scope", "priority", "palette"], str(ids))
    opts = [o for q in u["questions"] for o in q["options"]]
    check("no duplicate options, none multi-select", len(opts) == len(set(opts)) and not any(q["multi"] for q in u["questions"]))

    answers = [{"question_id": "budget", "answer": "₹30,000"}, {"question_id": "scope", "answer": u["questions"][1]["options"][1]},
               {"question_id": "priority", "answer": "Open floor space"}]
    r = timed("chat", lambda: c.post("/api/chat", json={"session_id": u["session_id"], "answers": answers, "message": ""}))
    check("answers accepted", r.status_code == 200 and r.json()["ready_to_generate"])
    r = timed("generate", lambda: c.post("/api/generate", json={"session_id": u["session_id"]}))
    check("generate ok", r.status_code == 200)
    links = []
    if r.status_code == 200:
        g, links = show_result("generate", r)
        if a["size_class"] == "small":
            titles = " ".join(m["title"].lower() for m in g["product_matches"])
            check("small room: no oversized products", not any(w in titles for w in ("3-seat", "sectional", "6-seater", "8x10")), titles)
        if OUT:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "before.jpg").write_bytes(c.get(u["image_url"]).content)
            (OUT / "after.png").write_bytes(c.get(g["generated_image_url"]).content)

    # ---- Modify Existing Room --------------------------------------------
    if "--no-modify" not in sys.argv:
        r = timed("modify", lambda: c.post("/api/modify", files=files(), data={
            "instruction": "Make it feel warmer and cosier with softer lighting", "budget": "₹20,000", "room_size": ROOM_SIZE}))
        check("modify ok", r.status_code == 200)
        if r.status_code == 200:
            m, more = show_result("modify", r)
            links += more
            if OUT:
                (OUT / "modify_after.png").write_bytes(c.get(m["generated_image_url"]).content)

    # ---- error paths -----------------------------------------------------
    r = c.post("/api/generate", json={"session_id": "nope"})
    check("unknown session -> clear 404 message", r.status_code == 404 and "start over" in r.json()["detail"].lower())
    r = c.post("/api/upload", data={"style": "Modern"}, files={"image": ("x.png", b"not an image" * 20, "image/png")})
    check("corrupt upload -> clear 415 message", r.status_code == 415 and "detail" in r.json())

    # ---- every shop link actually resolves --------------------------------
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
          "Accept-Language": "en-IN,en;q=0.9", "Accept": "text/html"}
    web = httpx.Client(headers=ua, timeout=30, follow_redirects=True)
    bad = []
    for url in sorted(set(links)):
        try:
            code = web.get(url).status_code
        except Exception as exc:  # noqa: BLE001
            code = repr(exc)
        if code != 200:
            bad.append((code, url))
    check(f"all {len(set(links))} shop links return a real page", not bad, str(bad[:4]))

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; FAILED: {failed}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

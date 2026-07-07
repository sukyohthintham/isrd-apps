#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ดึงรูปสินค้าจาก Zort ลงโฟลเดอร์ images/ อัตโนมัติ  (ตั้งชื่อไฟล์ตาม SKU)
*** ดึงเฉพาะ SKU ที่ใช้งานจริงในระบบ ISRD (จากหน้า Tracking) เท่านั้น ***
เพื่อไม่ให้โหลดรูปสินค้าทั้งหมดใน Zart (หลายพันรูป) จนโฟลเดอร์บวมเกินจำเป็น

วิธีใช้:
  1) เปิด Command Prompt:
        cd C:\\GitHub\\isrd-apps
        python pull_zort_images.py
  2) ใส่ storename / apikey / apisecret (จาก Zort: ตั้งค่า -> เชื่อมต่อ/Open API)
  3) เสร็จแล้ว Commit + Push ใน GitHub Desktop -> กด "ล้าง Cache รูป" ที่เว็บ

หมายเหตุ: ไม่เก็บรหัส API ลงไฟล์ (ถามตอนรันทุกครั้ง)
"""

import os, json, time, urllib.request, urllib.parse

API_BASE   = "https://open-api.zortout.com/v4"
FB_BASE    = "https://leave-system-ac0c6-default-rtdb.asia-southeast1.firebasedatabase.app/isrd2026"
OUT_DIR    = "images"
VALID_EXT  = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def sku_in_system():
    """รายชื่อ SKU ที่ใช้จริงในระบบ ISRD (ดึงจาก Firebase หน้า Tracking)"""
    with urllib.request.urlopen(FB_BASE + "/tracking.json", timeout=60) as r:
        trk = json.loads(r.read().decode("utf-8")) or {}
    skus = set()
    for v in trk.values():
        if isinstance(v, dict):
            s = (v.get("sku") or "").strip()
            if s:
                skus.add(s)
    return skus


def zort_image_map(headers, want):
    """สร้าง map { sku : imageURL } จาก Zort เฉพาะ SKU ที่อยู่ใน want"""
    mp, page = {}, 1
    while True:
        qs = urllib.parse.urlencode({"page": page, "limit": 500})
        with urllib.request.urlopen(
                urllib.request.Request(API_BASE + "/Product/GetProducts?" + qs, headers=headers),
                timeout=60) as r:
            lst = (json.loads(r.read().decode("utf-8")).get("list")) or []
        for p in lst:
            s = (p.get("sku") or "").strip()
            if s not in want:
                continue
            img = (p.get("imagepath") or "").strip()
            if not img:
                il = p.get("imageList") or []
                img = (il[0] if il else "").strip()
            if img:
                mp[s] = img
        print("   ...ดึง Zort หน้า %d (จับคู่ได้ %d/%d)" % (page, len(mp), len(want)))
        if len(lst) < 500:
            break
        page += 1
    return mp


def have_set():
    got = set()
    if os.path.isdir(OUT_DIR):
        for fn in os.listdir(OUT_DIR):
            b, e = os.path.splitext(fn)
            if e.lower() in VALID_EXT:
                got.add(b.strip())
    return got


def ext_of(url, ct=""):
    low = url.lower().split("?")[0]
    for e in VALID_EXT:
        if low.endswith(e):
            return e
    ct = ct.lower()
    if "jpeg" in ct or "jpg" in ct: return ".jpg"
    if "webp" in ct: return ".webp"
    if "gif" in ct: return ".gif"
    return ".png"


def main():
    print("=" * 58)
    print("  ดึงรูป Zort -> images/  (เฉพาะ SKU ที่ใช้ในระบบ ISRD)")
    print("=" * 58)
    storename = input("storename : ").strip()
    apikey    = input("apikey    : ").strip()
    apisecret = input("apisecret : ").strip()
    if not (storename and apikey and apisecret):
        print("!! ต้องใส่ครบ 3 ค่า"); return
    headers = {"storename": storename, "apikey": apikey, "apisecret": apisecret}
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\n[1] อ่าน SKU ที่ใช้ในระบบ (Firebase) ...")
    try:
        want = sku_in_system()
    except Exception as e:
        print("!! อ่าน Firebase ไม่ได้:", e); return
    print("    SKU ในระบบ: %d" % len(want))

    print("[2] จับคู่รูปจาก Zort ...")
    try:
        zmap = zort_image_map(headers, want)
    except Exception as e:
        print("!! เรียก Zort ไม่ได้ (เช็ค key):", e); return

    have = have_set()
    todo = {s: u for s, u in zmap.items() if s not in have}
    no_img = [s for s in want if s not in zmap and s not in have]
    print("    มีรูปแล้ว %d · จะดาวน์โหลด %d · ยังไม่มีรูปใน Zort %d\n"
          % (len(want) - len(todo) - len(no_img), len(todo), len(no_img)))

    print("[3] ดาวน์โหลด ...")
    ok = fail = 0
    for s, url in todo.items():
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                ct = r.headers.get("Content-Type", ""); data = r.read()
            open(os.path.join(OUT_DIR, s + ext_of(url, ct)), "wb").write(data)
            ok += 1
            print("    OK %-18s (%d KB)" % (s, len(data) // 1024))
            time.sleep(0.1)
        except Exception as e:
            fail += 1
            print("    FAIL %-18s %s" % (s, e))

    print("\n" + "=" * 58)
    print("  เสร็จ! ดาวน์โหลดใหม่ %d · ล้มเหลว %d" % (ok, fail))
    if no_img:
        print("  * มี %d SKU ที่ยังไม่มีรูปใน Zort — ต้องเพิ่มรูปใน Zort ก่อน แล้วรันซ้ำ" % len(no_img))
    print("=" * 58)
    print("\nต่อไป: GitHub Desktop -> Commit -> Push -> กด 'ล้าง Cache รูป' ที่เว็บ\n")
    input("กด Enter เพื่อปิด...")


if __name__ == "__main__":
    main()

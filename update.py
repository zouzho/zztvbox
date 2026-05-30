#!/usr/bin/env python3
"""
TVBox 聚合源自动更新
每小时 GitHub Actions 自动执行：
  1. tvbox.json       → 简洁版（采集站，播放测速排序）
  2. tvbox_full.json  → 全量版（399站合并，带spider）
  3. tvbox_multi.json → 多仓版（27个独立仓库）
"""
import json, sys, re, subprocess, os, time
from urllib.parse import urljoin, urlparse

WORK_DIR = os.path.dirname(os.path.abspath(__file__))

def curl(url, timeout=10):
    try:
        r = subprocess.run(["curl","-s","-L","--connect-timeout",str(timeout),
                           "--max-time",str(timeout*2),"-A","Mozilla/5.0",url],
                          capture_output=True, timeout=timeout*2+5)
        return r.stdout.decode("utf-8", errors="replace")
    except: return ""

def parse_json(raw):
    raw = raw.lstrip('﻿'); raw = re.sub(r',(\s*[}\]])', r'\1', raw)
    try: return json.loads(raw, strict=False)
    except:
        s,e = raw.find('{'), raw.rfind('}')
        if s>=0 and e>s:
            try: return json.loads(raw[s:e+1], strict=False)
            except: pass
    return None

def resolve_spider(spider, source_url):
    if not spider: return ""
    if spider.startswith("http"): return spider
    if spider.startswith("./"):
        p = urlparse(source_url)
        return f"{p.scheme}://{p.netloc}{spider[1:]}"
    return spider

def resolve_url(base, path):
    if path.startswith("http"): return path
    if path.startswith("/"): return f"{urlparse(base).scheme}://{urlparse(base).netloc}{path}"
    return urljoin(base, path)

def extract_m3u8(t):
    return re.findall(r'(https?://[^\s"\'<>#\$]+?\.m3u8)', t)

def get_segments(media, media_url):
    urls = []
    lines = media.strip().split("\n")
    for i, line in enumerate(lines):
        if line.startswith("#EXTINF") and i+1 < len(lines):
            nxt = lines[i+1].strip()
            if nxt and not nxt.startswith("#"):
                urls.append(resolve_url(media_url, nxt))
    return urls

def build_url(base, params):
    return base.rstrip("/") + ("&" if "?" in base else "?") + params

def test_play_speed(api, stype):
    """真实播放测速：m3u8主列表→媒体列表→ts分片下载"""
    base = re.sub(r'[?&]ac=list.*', '', api.rstrip("/"))
    body = curl(build_url(base, "ac=list"), 10)
    if not body or len(body) < 50: return 0, 0, "列表失败"
    vid = None
    if stype == 0:
        m = re.findall(r'<id>(\d+)</id>', body)
        vid = m[0] if m else None
    else:
        try:
            j = json.loads(body, strict=False)
            vid = str(j["list"][0]["vod_id"]) if j.get("list") else None
        except: return 0, 0, "解析失败"
    if not vid: return 0, 0, "无ID"
    detail = curl(build_url(base, f"ac=detail&ids={vid}"), 10)
    play = None
    if stype == 0:
        u = extract_m3u8(detail); play = u[0] if u else None
    else:
        try:
            dj = json.loads(detail, strict=False)
            vl = dj.get("list", [])
            if vl: u = extract_m3u8(vl[0].get("vod_play_url", "")); play = u[0] if u else None
        except: return 0, 0, "详情失败"
    if not play: return 0, 0, "无播放URL"
    t0 = time.time()
    master = curl(play, 10)
    ttfb = int((time.time() - t0) * 1000)
    if not master: return ttfb, 0, "主列表空"
    media_url = None
    if "#EXT-X-STREAM-INF" in master:
        lines = master.strip().split("\n")
        for i, line in enumerate(lines):
            if "STREAM-INF" in line and i + 1 < len(lines):
                sub = lines[i + 1].strip()
                if sub and not sub.startswith("#"):
                    media_url = resolve_url(play, sub); break
    elif "#EXTINF" in master: media_url = play
    if not media_url: return ttfb, 0, "无媒体列表"
    t1 = time.time()
    media = curl(media_url, 10)
    mms = int((time.time() - t1) * 1000)
    if "#EXTINF" not in media: return ttfb + mms, 0, "无分片"
    segs = get_segments(media, media_url)
    if not segs: return ttfb + mms, 0, "无分片"
    tb, tt, ok = 0, 0, 0
    for s in segs[:3]:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null",
                           "-w", "%{http_code},%{size_download},%{time_total}",
                           "--connect-timeout", "5", "--max-time", "15", s],
                          capture_output=True, timeout=20)
        parts = r.stdout.decode().strip().split(",")
        code = parts[0] if parts else "000"
        sz = int(float(parts[1])) if len(parts) > 1 and parts[1] else 0
        dl = float(parts[2]) if len(parts) > 2 and parts[2] else 99
        if code.startswith("2") and sz > 1000: tb += sz; tt += dl; ok += 1
    if ok == 0: return ttfb + mms, 0, "分片失败"
    speed = int((tb / 1024) / tt) if tt > 0 else 0
    return ttfb + mms, speed, "OK"

def main():
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] 开始更新...")

    # ── 1. 获取源列表 ──
    html = curl("https://tvbox.clbug.com/user.php", 20)
    src_urls = re.findall(r'data-url="([^"]+)"', html)
    src_names = re.findall(r'<td class="td-name">([^<]+)</td>', html)
    sources = [(n.strip(), u.strip().replace("&amp;", "&"))
               for n, u in zip(src_names, src_urls)
               if u.strip() and not u.strip().startswith("#")]
    print(f"  源列表: {len(sources)}")

    # ── 2. 测延迟 + 抓取 ──
    available = []
    for name, url in sources:
        try:
            t0 = time.time()
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                               "--connect-timeout", "5", "--max-time", "10",
                               "-L", "-A", "Mozilla/5.0", url],
                              capture_output=True, timeout=15)
            code = r.stdout.decode().strip()
            lat = int((time.time() - t0) * 1000) if code.startswith(("2", "3")) else 99999
        except: lat = 99999
        if lat < 99999: available.append((name, url, lat))
        sys.stdout.write(f"\r  测速: {len(available)}/{len(sources)}"); sys.stdout.flush()
    print()
    available.sort(key=lambda x: x[2])
    print(f"  可用: {len(available)}")

    # ── 3. 抓取并合并所有源 ──
    all_sites, all_lives, all_parses = [], [], []
    site_keys, live_keys, parse_keys = set(), set(), set()
    spider_jars = {}
    # 记录每个采集站来自哪个源
    collect_sources = {}  # api -> (source_name, stype)

    for name, url, lat in available:
        sys.stdout.write(f"\r  合并: {name} ({lat}ms)"); sys.stdout.flush()
        data = parse_json(curl(url, 15))
        if not data: continue

        spider = data.get("spider", "")
        if spider:
            abs_spider = resolve_spider(spider, url)
            spider_jars[abs_spider] = spider_jars.get(abs_spider, 0) + 1

        for s in (data.get("sites") or []):
            key = s.get("key", "")
            if not key or key in site_keys: continue
            site_keys.add(key)
            s["name"] = f"[{lat}ms|{name}] {s.get('name', key)}"
            s["_lat"] = lat
            all_sites.append(s)
            # 记录采集站
            st = s.get("type", -1)
            api = s.get("api", "")
            if st in (0, 1) and api.startswith("http") and api not in collect_sources:
                collect_sources[api] = (name, st)

        for l in (data.get("lives") or []):
            u = l.get("url", "")
            if u and u not in live_keys: live_keys.add(u); all_lives.append(l)
        for p in (data.get("parses") or []):
            u = p.get("url", "")
            if u and u not in parse_keys: parse_keys.add(u); all_parses.append(p)
    print()

    # 按延迟排序
    all_sites.sort(key=lambda x: x.get("_lat", 99999))
    for s in all_sites: s.pop("_lat", None)

    # ── 4. 生成 tvbox_full.json（全量版）──
    best_spider = max(spider_jars, key=spider_jars.get) if spider_jars else ""
    full_json = {"spider": best_spider, "sites": all_sites, "lives": all_lives, "parses": all_parses}
    with open(os.path.join(WORK_DIR, "tvbox_full.json"), "w", encoding="utf-8") as f:
        json.dump(full_json, f, ensure_ascii=False, indent=2)
    types = {}
    for s in all_sites: types[s.get("type", -1)] = types.get(s.get("type", -1), 0) + 1
    print(f"  全量版: {len(all_sites)} 站点 (采集:{types.get(0,0)+types.get(1,0)} 爬虫:{types.get(3,0)})")

    # ── 5. 生成 tvbox_multi.json（多仓版）──
    multi = {"storeHouse": [{"sourceName": f"[{lat}ms] {name}", "sourceUrl": url}
                            for name, url, lat in available]}
    with open(os.path.join(WORK_DIR, "tvbox_multi.json"), "w", encoding="utf-8") as f:
        json.dump(multi, f, ensure_ascii=False, indent=2)
    print(f"  多仓版: {len(available)} 个仓库")

    # ── 6. 生成 tvbox.json（简洁版，采集站播放测速排序）──
    print(f"  简洁版: 测 {len(collect_sources)} 个采集站播放速度...")
    collect_results = []
    for api, (src_name, stype) in collect_sources.items():
        ttfb, speed, status = test_play_speed(api, stype)
        if status == "OK":
            collect_results.append((ttfb, speed, api, stype))
        sys.stdout.write(f"\r  {len(collect_results)} 可用/{len(collect_sources)} 测试"); sys.stdout.flush()
    print()

    # 按持续速度排序（速度快→慢，同速按首帧快）
    collect_results.sort(key=lambda x: (-x[1], x[0]))

    collect_sites = []
    for ttfb, speed, api, stype in collect_results:
        # 从全量站点中找名称
        clean_name = api.split("/")[2]
        for s in all_sites:
            if s.get("api") == api:
                clean_name = re.sub(r'^\[.*?\]\s*', '', s.get("name", clean_name))
                break
        stable = "稳" if speed > 500 else "中" if speed > 100 else "慢"
        collect_sites.append({
            "key": clean_name,
            "name": f"[{speed}KB/s|{ttfb}ms|{stable}] {clean_name}",
            "type": stype, "api": api,
            "searchable": 1, "quickSearch": 1, "filterable": 0
        })

    collect_json = {"spider": "", "sites": collect_sites, "lives": [], "parses": []}
    with open(os.path.join(WORK_DIR, "tvbox.json"), "w", encoding="utf-8") as f:
        json.dump(collect_json, f, ensure_ascii=False, indent=2)

    for i, (ttfb, speed, api, _) in enumerate(collect_results, 1):
        stable = "🟢" if speed > 500 else "🟡" if speed > 100 else "🔴"
        host = api.split("/")[2][:25]
        print(f"    #{i} [{speed}KB/s|{ttfb}ms] {stable} {host}")

    # ── 7. 源列表 ──
    with open(os.path.join(WORK_DIR, "sources.txt"), "w") as f:
        f.write(f"# {ts}\n\n")
        for name, url, lat in available: f.write(f"[{lat}ms] {name}\n{url}\n\n")

    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完成!")
    return 0

if __name__ == "__main__": sys.exit(main())

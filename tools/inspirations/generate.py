"""Run Replicate image jobs in parallel and download the results.

usage: python tools/inspirations/generate.py jobs.json outdir
jobs.json: [{"id": "...", "model": "owner/name", "input": {...}}]
Any string "@slab:<name>" inside input is replaced by a data URI of
assets/img/slab-<name>.jpg.
"""
import base64, json, os, sys, time, urllib.request, concurrent.futures as cf

TOKEN = os.environ["REPLICATE_API_TOKEN"]
SLABS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "img", "")


def api(method, url, body=None):
    for attempt in range(12):
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 0) + 5 + attempt * 3)
    raise RuntimeError("still rate limited")


def resolve(v):
    if isinstance(v, str) and v.startswith("@slab:"):
        data = open(SLABS + f"slab-{v[6:]}.jpg", "rb").read()
        return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    if isinstance(v, str) and v.startswith("@file:"):
        p = v[6:]
        mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(open(p, "rb").read()).decode()
    if isinstance(v, list):
        return [resolve(x) for x in v]
    if isinstance(v, dict):
        return {k: resolve(x) for k, x in v.items()}
    return v


def run(job, outdir):
    p = api("POST", f"https://api.replicate.com/v1/models/{job['model']}/predictions", {"input": resolve(job["input"])})
    t0 = time.time()
    while p["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(4)
        p = api("GET", p["urls"]["get"])
        if time.time() - t0 > 600:
            return job["id"], "timeout"
    if p["status"] != "succeeded":
        return job["id"], f"{p['status']}: {p.get('error')}"
    out = p["output"]
    urls = out if isinstance(out, list) else [out]
    saved = []
    for i, u in enumerate(urls):
        ext = u.rsplit(".", 1)[-1].split("?")[0][:4]
        path = os.path.join(outdir, f"{job['id']}{'' if i == 0 else '-' + str(i)}.{ext}")
        urllib.request.urlretrieve(u, path)
        saved.append(os.path.basename(path))
    return job["id"], f"ok {round(time.time() - t0)}s {saved} predict_time={p.get('metrics', {}).get('predict_time')}"


if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1]))
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    done = {f.rsplit(".", 1)[0] for f in os.listdir(outdir)}
    jobs = [j for j in jobs if j["id"] not in done]
    print(len(jobs), "to run", flush=True)
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(run, j, outdir) for j in jobs]
        for f in cf.as_completed(futs):
            try:
                print(*f.result(), flush=True)
            except Exception as e:
                print("ERR", e, flush=True)

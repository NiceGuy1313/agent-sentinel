#!/usr/bin/env python3
# Multi-SLM audit benchmark via NVIDIA NIM (OpenAI-compatible).
# Replays the SAME 117 audit queries (agent-derived) against many models and
# records each model's action_is_safe verdict. No agent/eBPF re-run.
import json, os, re, sys, time, urllib.request, urllib.error, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/home/agentsentinel/test/agent-sentinel"
QUERIES = json.load(open(os.path.join(HERE, "audit_queries.json")))
SYS = open(os.path.join(HERE, "sys_prompt.txt")).read()
OUT = os.path.join(HERE, "nvidia_results.jsonl")

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
KEY = os.getenv("NVIDIA_API_KEY", "")
if not KEY and os.path.exists(os.path.join(ROOT, ".env")):
    for l in open(os.path.join(ROOT, ".env")):
        if l.startswith("NVIDIA_API_KEY="):
            KEY = l.strip().split("=", 1)[1]
assert KEY, "NVIDIA_API_KEY not set (env or .env)"

# probe-confirmed discriminating models (attack->UNSAFE, benign->SAFE)
MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "z-ai/glm-5.2",                                 # slow (~55s/call) but wanted
    "deepseek-ai/deepseek-v4-pro",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "minimaxai/minimax-m3",
    "google/gemma-4-31b-it",
    "nvidia/nvidia-nemotron-nano-9b-v2",
]

def http_json(body, timeout=600, retries=4):
    data = json.dumps(body).encode()
    hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Accept": "application/json"}
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(NVIDIA_URL, data=data, headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r), None
        except urllib.error.HTTPError as e:
            code = e.code; last = f"HTTP{code}"
            if code in (429, 500, 502, 503, 504):
                time.sleep(3 * (a + 1)); continue
            return None, f"HTTP{code}"
        except Exception as e:
            last = type(e).__name__; time.sleep(2 * (a + 1))
    return None, last

def parse_verdict(msg):
    txt = (msg.get("content") or "")
    if "{" not in txt:
        txt = (msg.get("reasoning_content") or "") + txt
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < i: return "NO_JSON"
    try:
        v = json.loads(txt[i:j+1]).get("action_is_safe")
        return "SAFE" if v is True else "UNSAFE" if v is False else "?"
    except Exception:
        return "PARSE_FAIL"

def ask(model, prompt):
    d, err = http_json({
        "model": model, "max_tokens": 4096, "temperature": 0.0,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
    })
    if err: return "ERR:" + err
    try:
        return parse_verdict(d["choices"][0]["message"])
    except Exception as e:
        return "ERR:parse-" + type(e).__name__

def main():
    open(OUT, "w").close()
    print(f"replaying {len(QUERIES)} queries x {len(MODELS)} models", flush=True)
    for model in MODELS:
        t0 = time.time(); done = 0
        probe = ask(model, "Reply with JSON {\"action_is_safe\": true}")
        if isinstance(probe, str) and probe.startswith("ERR"):
            print(f"[SKIP] {model}: {probe}", flush=True); continue
        print(f"[RUN ] {model} ...", flush=True)
        with cf.ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(ask, model, q["prompt"]): (i, q) for i, q in enumerate(QUERIES)}
            for fut in cf.as_completed(futs):
                i, q = futs[fut]; v = fut.result(); done += 1
                with open(OUT, "a") as f:
                    f.write(json.dumps({"model": model, "idx": i, "is_attack": q["is_attack"],
                                        "sensop": q["sensop"][:160], "verdict": v}) + "\n")
        print(f"[DONE] {model}: {done} queries in {time.time()-t0:.0f}s", flush=True)
    print("ALL DONE ->", OUT, flush=True)

if __name__ == "__main__":
    main()

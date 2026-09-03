#!/usr/bin/env python3
# Offline audit-LLM benchmark: send identical (system prompt + audit query) to
# Claude and gpt-oss, parse each verdict. Isolates the auditor as the only var.
import json, os, re, sys, time, urllib.request, concurrent.futures as cf

SCR = os.path.dirname(os.path.abspath(__file__))
ROOT = "/home/agentsentinel/test/agent-sentinel"
QUERIES = json.load(open(os.path.join(SCR, "audit_queries.json")))
SYS = open(os.path.join(SCR, "sys_prompt.txt")).read()
OUT = os.path.join(SCR, "replay_results.jsonl")

# creds
env = dict(l.strip().split("=",1) for l in open(os.path.join(ROOT,".env")) if "=" in l)
ANTHROPIC_KEY = env["ANTHROPIC_API_KEY"]
OLLAMA_URL = env.get("OPENAI_BASE_URL","http://192.168.56.1:11434/v1").rstrip("/") + "/chat/completions"

def http_json(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def parse_verdict(text):
    if not text: return ("EMPTY", None)
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i: return ("NO_JSON", None)
    try:
        obj = json.loads(text[i:j+1])
        v = obj.get("action_is_safe")
        return ("SAFE" if v is True else "UNSAFE" if v is False else "?", obj)
    except Exception:
        return ("PARSE_FAIL", None)

def ask_claude(prompt):
    try:
        d = http_json("https://api.anthropic.com/v1/messages",
            {"x-api-key": ANTHROPIC_KEY, "anthropic-version":"2023-06-01", "content-type":"application/json"},
            {"model":"claude-sonnet-4-5-20250929","max_tokens":1024,"system":SYS,
             "messages":[{"role":"user","content":prompt}]}, 60)
        txt = "".join(b.get("text","") for b in d.get("content",[]) if b.get("type")=="text")
        return parse_verdict(txt)
    except Exception as e:
        return ("ERROR:"+type(e).__name__, None)

def ask_gptoss(prompt):
    try:
        d = http_json(OLLAMA_URL,
            {"Authorization":"Bearer ollama","Content-Type":"application/json"},
            {"model":"gpt-oss:20b","max_tokens":2048,
             "messages":[{"role":"system","content":SYS},{"role":"user","content":prompt}]}, 300)
        txt = d["choices"][0]["message"].get("content","")
        return parse_verdict(txt)
    except Exception as e:
        return ("ERROR:"+type(e).__name__, None)

def run_one(idx_q):
    idx, q = idx_q
    cv, cobj = ask_claude(q["prompt"])
    gv, gobj = ask_gptoss(q["prompt"])
    return {"idx":idx, "is_attack":q["is_attack"], "src":q["src"],
            "sensop": q["sensop"].replace("\n"," ")[:160],
            "claude": cv, "gptoss": gv}

def main():
    open(OUT,"w").close()
    print(f"replaying {len(QUERIES)} queries x 2 backends", flush=True)
    done=0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs=[ex.submit(run_one,(i,q)) for i,q in enumerate(QUERIES)]
        for fut in cf.as_completed(futs):
            r=fut.result(); done+=1
            with open(OUT,"a") as f: f.write(json.dumps(r)+"\n")
            if done%10==0 or done==len(QUERIES):
                print(f"  {done}/{len(QUERIES)} done", flush=True)
    print("DONE ->", OUT, flush=True)

if __name__=="__main__":
    main()

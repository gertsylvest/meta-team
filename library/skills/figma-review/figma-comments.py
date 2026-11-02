#!/usr/bin/env python3
"""Read (and reply to) Figma comments, resolved onto MCP-editable node ids.

Why this exists: the Figma MCP server has no comments API, so operator feedback
pinned on the canvas is invisible to the agent. The REST API does expose comments,
and a pinned comment's `client_meta.node_id` is the *same* id form `use_figma`
takes (e.g. "188:3") — so a pinned comment maps straight onto an editable node.

Auth: a Figma personal access token, read from (in order)
  1. $FIGMA_PAT
  2. ~/.config/figma/pat          (chmod 600; first line)
The token is never printed, logged or passed on the command line.

File: the file key comes from --file or $FIGMA_FILE_KEY (no baked-in default).
It is the KEY in https://figma.com/design/<KEY>/<name>.

Usage
  figma-comments.py list [--all] [--json] [--file KEY]
  figma-comments.py show <comment_id> [--file KEY]
  figma-comments.py reply <comment_id> <text> [--file KEY]
  figma-comments.py nodes <comment_id> [--file KEY]      # just the node ids, for piping

Notes / limits
  - The REST API cannot mark a comment RESOLVED (no endpoint). `list` shows
    unresolved by default and flags resolved ones with --all; resolve in the UI.
  - Comments dropped on empty canvas carry only x/y. Those are hit-tested against
    the file's node boxes and reported as `~approx` with the deepest containing node.
"""
import json, os, sys, time, urllib.request, urllib.error, argparse, pathlib

API = "https://api.figma.com/v1"
DEFAULT_FILE = os.environ.get("FIGMA_FILE_KEY", "").strip()
CACHE_DIR = pathlib.Path(os.path.expanduser("~/.cache/figma-comments"))
CACHE_TTL = 600  # seconds


def token():
    t = os.environ.get("FIGMA_PAT", "").strip()
    if t:
        return _clean(t)
    p = pathlib.Path(os.path.expanduser("~/.config/figma/pat"))
    if p.is_file():
        for line in p.read_text().splitlines():
            line = _clean(line)
            if line:
                return line
        sys.exit(
            f"{p} exists but is EMPTY — the token did not save.\n"
            "Write it with:  cat > ~/.config/figma/pat   (paste, Enter, Ctrl-D)\n"
            "Then check:     wc -c < ~/.config/figma/pat   (expect ~40-100 bytes)"
        )
    sys.exit(
        "No Figma token. Set FIGMA_PAT, or put it in ~/.config/figma/pat "
        "(chmod 600). Create one at figma.com → Settings → Security → "
        "Personal access tokens (scopes: file_comments:write, file_content:read)."
    )


def _clean(t):
    """Tolerate a token pasted with quotes, a KEY= prefix, or stray whitespace."""
    t = t.strip().strip('"').strip("'")
    if "=" in t and not t.startswith("fig"):
        t = t.split("=", 1)[1].strip().strip('"').strip("'")
    return t


def call(path, method="GET", body=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        headers={"X-Figma-Token": token(), "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        sys.exit(f"Figma API {e.code} on {method} {path}\n{detail}")


def file_index(key, use_cache=True):
    """node_id -> {name, type, path, box}. Cached briefly; the tree is big."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache = CACHE_DIR / f"{key}.json"
    doc = None
    if use_cache and cache.is_file() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        doc = json.loads(cache.read_text())
    if doc is None:
        doc = call(f"/files/{key}")
        # atomic, and private: the cache is a full dump of the design file
        tmp = cache.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc))
        os.chmod(tmp, 0o600)
        tmp.replace(cache)
    idx = {}

    def walk(n, trail):
        here = trail + [n.get("name", "?")]
        idx[n["id"]] = {
            "name": n.get("name", "?"),
            "type": n.get("type", "?"),
            "path": " ▸ ".join(here[1:]) or n.get("name", "?"),
            "depth": len(here),
            "box": n.get("absoluteBoundingBox"),
        }
        for c in n.get("children", []) or []:
            walk(c, here)

    walk(doc["document"], [])
    return idx


def hit_test(idx, x, y):
    """Deepest node whose box contains (x, y) — greatest tree depth wins.

    Depth is the node's real distance from the document root, not the length of
    its name path: one long-named top-level frame must not out-rank a genuinely
    nested child.
    """
    best, best_depth = None, -1
    for nid, meta in idx.items():
        b = meta.get("box")
        if not b:
            continue
        if b["x"] <= x <= b["x"] + b["width"] and b["y"] <= y <= b["y"] + b["height"]:
            if meta.get("depth", 0) > best_depth:
                best, best_depth = nid, meta.get("depth", 0)
    return best


def anchor(c, idx):
    """Resolve a comment to (node_id, how) where how is 'pinned' or '~approx'."""
    m = c.get("client_meta") or {}
    if m.get("node_id"):
        return m["node_id"], "pinned"
    if "x" in m and "y" in m:
        return hit_test(idx, m["x"], m["y"]), "~approx"
    return None, "unanchored"


def load(key, want_all, use_cache=True, want_replies=False):
    raw = call(f"/files/{key}/comments").get("comments", [])
    idx = file_index(key, use_cache)
    roots = {c["id"]: c for c in raw if not c.get("parent_id")}
    out = []
    for c in raw:
        parent_id = c.get("parent_id") or None
        # Figma stamps resolved_at on the THREAD ROOT only, and a reply carries no
        # pin of its own — so a reply inherits both from its root. Without this a
        # resolved thread's replies survive the filter and get hit-tested onto
        # whatever node happens to sit under (0,0), which is how a finished review
        # round comes back looking like 13 open ones.
        root = roots.get(parent_id) if parent_id else c
        if not want_replies and parent_id:
            continue
        if (root or c).get("resolved_at") and not want_all:
            continue
        nid, how = anchor(root or c, idx)
        meta = idx.get(nid, {}) if nid else {}
        out.append(
            {
                "id": c["id"],
                "parent_id": parent_id,
                "author": (c.get("user") or {}).get("handle", "?"),
                "created_at": c.get("created_at", "")[:19].replace("T", " "),
                "resolved": bool((root or c).get("resolved_at")),
                "message": (c.get("message") or "").strip(),
                "node_id": nid,
                "anchor": how,
                "node_name": meta.get("name"),
                "node_type": meta.get("type"),
                "node_path": meta.get("path"),
            }
        )
    out.sort(key=lambda c: c["created_at"])
    return out


def render(cs):
    if not cs:
        print("No unresolved comments.")
        return
    for i, c in enumerate(cs, 1):
        head = f"#{i}  [{c['created_at']}]  {c['author']}"
        if c["resolved"]:
            head += "  (RESOLVED)"
        if c["parent_id"]:
            head += f"  (reply to {c['parent_id']})"
        print(head)
        if c["node_id"]:
            print(f"    node  {c['node_id']}  \"{c['node_name']}\"  [{c['node_type']}]  {c['anchor']}")
            if c["node_path"]:
                print(f"    path  {c['node_path']}")
        else:
            print(f"    node  —  {c['anchor']}")
        for line in c["message"].splitlines() or [""]:
            print(f"    | {line}")
        print(f"    id    {c['id']}")
        print()


def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["list", "show", "reply", "nodes"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--file", default=DEFAULT_FILE, help="Figma file key")
    ap.add_argument("--all", action="store_true", help="include resolved")
    ap.add_argument("--replies", action="store_true", help="include replies (list shows threads only)")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--no-cache", action="store_true", help="refetch the file tree")
    a = ap.parse_args()
    use_cache = not a.no_cache
    if not a.file:
        sys.exit(
            "No Figma file key. Pass --file KEY, or set $FIGMA_FILE_KEY "
            "(projects usually set it in .claude/settings.json under env).\n"
            "The key is the KEY in https://figma.com/design/<KEY>/<name>."
        )

    if a.cmd == "list":
        cs = load(a.file, a.all, use_cache, want_replies=a.replies)
        print(json.dumps(cs, indent=2)) if a.json else render(cs)

    elif a.cmd in ("show", "nodes"):
        if not a.args:
            sys.exit(f"{a.cmd} needs a comment id")
        cs = [c for c in load(a.file, True, use_cache, want_replies=True) if c["id"] == a.args[0]]
        if not cs:
            sys.exit("No such comment id")
        if a.cmd == "nodes":
            print(cs[0]["node_id"] or "")
        else:
            print(json.dumps(cs[0], indent=2)) if a.json else render(cs)

    elif a.cmd == "reply":
        if len(a.args) < 2:
            sys.exit('reply needs: <comment_id> "<text>"')
        cid, text = a.args[0], " ".join(a.args[1:])
        r = call(f"/files/{a.file}/comments", "POST", {"message": text, "comment_id": cid})
        print(f"replied: {r.get('id')}")


if __name__ == "__main__":
    main()

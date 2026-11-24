"""Verify the exact publication, without regenerating or modifying any report."""
import argparse
from datetime import date
import hashlib
from pathlib import Path
import sys
from time import sleep
from urllib.request import Request, urlopen

from generate_brief import read_json, require, template

PUBLIC = "https://danielhsu329.github.io/Danielhsu--Morning--brief/"
MAX_BYTES = 1_000_000

def verify(read, issue, expected_sha):
    require(date.fromisoformat(issue).isoformat() == issue, "invalid issue date")
    slug = issue.replace("-", "")
    latest = read("data/latest.json")
    require(hashlib.sha256(latest).hexdigest() == expected_sha, "latest hash mismatch")
    require(read(f"data/{issue}.json") == latest, "dated JSON differs from latest")
    data = read_json(latest.decode("utf-8"))
    require(data["meta"]["date"] == issue, "incorrect latest issue date")
    manifest = read_json(read("data/manifest.json").decode("utf-8"))
    dates = manifest["dates"]
    require(type(dates) is list and bool(dates) and all(type(d) is str and date.fromisoformat(d).isoformat() == d for d in dates),
            "invalid archive dates")
    require(manifest["latest"] == dates[0] == issue and dates == sorted(set(dates), reverse=True)
            and manifest["updated_at"] == data["meta"]["cutoff_taipei"], "manifest mismatch")
    for path in ("", f"archive/{slug}.html"):
        _, embedded, _ = template(read(path).decode("utf-8"))
        require(embedded == data, "HTML embedded data differs: " + (path or "homepage"))
    directory = read("archive/").decode("utf-8")
    require(all(f'href="{d.replace("-", "")}.html"' in directory for d in dates),
            "missing archive link")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--issue", required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--commit", required=True)
    a=p.parse_args()
    require(len(a.commit)==40 and all(c in "0123456789abcdef" for c in a.commit), "invalid commit")
    require(len(a.expected_sha)==64 and all(c in "0123456789abcdef" for c in a.expected_sha), "invalid digest")
    def read(path):
        url = PUBLIC + path + "?v=" + a.commit
        with urlopen(Request(url,headers={"User-Agent":"MorningBrief-public-readback/1","Cache-Control":"no-cache"}),timeout=8) as r:
            require(r.geturl().startswith(PUBLIC), "unexpected Pages redirect")
            raw=r.read(MAX_BYTES + 1)
            require(len(raw)<=MAX_BYTES, "unexpectedly large response")
            return raw
    for attempt in range(6):
        try:
            verify(read, a.issue, a.expected_sha)
            print("Verified live homepage, dated archive and JSON, manifest, archive links", a.issue)
            return 0
        except (OSError, ValueError, TypeError, KeyError):
            if attempt<5: sleep(8)
    print("Live verification failed; inspect the existing deployment without regenerating Gemini.",file=sys.stderr)
    return 1

if __name__=="__main__": sys.exit(main())

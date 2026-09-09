"""Pivots/rebrands manually CURATED from the stitched detector.

Each entry is a MANUAL judgment (I read the titles/h1/content of the snapshots
in the months of greatest variation and at the domain boundaries) about whether
there was a product PIVOT or a REBRAND, with the date pinned down via Wayback.
The `domain`+`date` fields are used to resolve the exact snapshot (wayback_url)
that becomes the SOURCE of the chip on the site.

Source of truth: data/curated_trajectories.json
Output: data/pivots_curated.json
"""
from __future__ import annotations
import json
import common

# Fuente de verdad: data/curated_trajectories.json (editable a mano o escrito por
# el loop trajectory-loop al cerrar PASS).
# Schema: [{slug, type: "pivot"|"rebrand", date: "YYYY-MM", domain, title, prose}, ...]
CURATED_PATH = common.DATA_DIR / "curated_trajectories.json"
_CURATED_DICTS = json.loads(CURATED_PATH.read_text(encoding="utf-8"))
CURATED = [
    (c["slug"], c["type"], c["date"], c["domain"], c["title"], c["prose"])
    for c in _CURATED_DICTS
]



def resolve_wayback(domain: str, date: str) -> tuple[str | None, str | None]:
    """Returns (timestamp, view_url) of the snapshot for the month `date` (or the closest one).
    `domain` can be a domain (data/wayback/<dom>) or 'profile:<slug>' for the
    Platanus profile (data/wayback_platanus/<slug>)."""
    if domain.startswith("profile:"):
        mf = common.DATA_DIR / "wayback_platanus" / domain.split(":", 1)[1] / "manifest.json"
    else:
        mf = common.DATA_DIR / "wayback" / domain / "manifest.json"
    if not mf.exists():
        return None, None
    snaps = json.loads(mf.read_text(encoding="utf-8")).get("snapshots", [])
    snaps = [s for s in snaps if s.get("timestamp")]
    if not snaps:
        return None, None
    target = date.replace("-", "")  # YYYYMM
    # snapshot whose YYYYMM == target, otherwise the first >= target, otherwise the last
    exact = [s for s in snaps if s["timestamp"][:6] == target]
    pick = exact[0] if exact else next((s for s in snaps if s["timestamp"][:6] >= target), snaps[-1])
    return pick["timestamp"], pick.get("wayback_url")


def main() -> None:
    out = []
    for slug, typ, date, domain, title, prose in CURATED:
        ts, url = resolve_wayback(domain, date)
        out.append({"slug": slug, "type": typ, "date": date, "domain": domain,
                    "title": title, "prose": prose,
                    "wayback_ts": ts, "wayback_url": url})
        flag = "" if url else "  ⚠ sin snapshot"
        print(f"  {slug:14} {typ:8} {date}  {domain:22} ts={ts}{flag}")
    (common.DATA_DIR / "pivots_curated.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✔ {len(out)} pivots/rebrands curados → data/pivots_curated.json")
    print(f"  con wayback_url: {sum(1 for o in out if o['wayback_url'])}/{len(out)}")


if __name__ == "__main__":
    main()

"""Phase 1 exploration: for each feature route, screenshot the base state and
dump a structured inventory of interactive elements (headings, buttons, inputs,
selects, tabs). Deterministic, read-only driving — does NOT submit/delete.

Run: GUIDE_BASE=http://localhost:5173 python tools/guide/explore.py
Outputs:
  docs/screenshots/guide/<slug>/00-base.png   (per feature base state)
  docs/.guide-notes.json                       (machine inventory)
  docs/.guide-notes.md                         (readable inventory)
"""
import json
import os
from _lib import browser, login, SHOTS

# (slug, route, label) — order grouped logically
ROUTES = [
    ("dashboard",        "/",                     "Dashboard"),
    ("executive",        "/executive",            "Executive"),
    ("menu-planner",     "/menu-planner",         "Menu Planner"),
    ("build-manual",     "/menu-manual",          "Build Manual"),
    ("menu-approval",    "/menu-approval",        "Approval Menu"),
    ("nutrisi",          "/nutrisi",              "Nutrisi Harian"),
    ("purchase-orders",  "/purchase-orders",      "Purchase Orders"),
    ("inspections",      "/inspections",          "Joint Inspection"),
    ("receiving",        "/receiving",            "Receiving (Quick)"),
    ("production",       "/production",           "Production"),
    ("distributions",    "/distributions",        "Distribusi"),
    ("aslap",            "/aslap",                "ASLAP Daily"),
    ("scan-errors",      "/scan-errors",          "Scan Errors"),
    ("variance",         "/reports/variance",     "Variance Report"),
    ("finance",          "/finance",              "Akuntan Finance"),
    ("admin-schools",    "/admin/schools",        "Master Sekolah"),
    ("admin-suppliers",  "/admin/suppliers",      "Master Supplier"),
    ("admin-users",      "/admin/users",          "Users"),
    ("admin-kitchens",   "/admin/kitchens",       "Kitchens"),
    ("admin-overview",   "/admin/overview",       "All Kitchens"),
    ("admin-orgs",       "/admin/organizations",  "Organizations"),
]

INVENTORY_JS = r"""
() => {
  const t = el => (el.innerText || el.textContent || '').trim().replace(/\s+/g,' ').slice(0,80);
  const vis = el => { const r = el.getBoundingClientRect(); return r.width>0 && r.height>0; };
  const headings = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(t).filter(Boolean);
  const buttons = [...document.querySelectorAll('button')].filter(vis).map(t).filter(Boolean);
  const links = [...document.querySelectorAll('a[href]')].filter(vis)
      .map(a => ({text: t(a), href: a.getAttribute('href')}))
      .filter(x => x.text && !x.href.startsWith('http'));
  const inputs = [...document.querySelectorAll('input,textarea')].filter(vis).map(i => ({
      type: i.type || i.tagName.toLowerCase(),
      name: i.name || i.id || '',
      placeholder: i.placeholder || '',
  }));
  const selects = [...document.querySelectorAll('select')].filter(vis).map(s => ({
      name: s.name || s.id || '',
      options: [...s.options].map(o => o.text.trim()).slice(0,12),
  }));
  // tab-like: role=tab, or buttons inside a tablist, or common tab class patterns
  const tabs = [...document.querySelectorAll('[role="tab"]')].filter(vis).map(t).filter(Boolean);
  return {headings, tabs, buttons, links, inputs, selects};
}
"""


def main():
    p, b, ctx = browser(headless=True)
    page = ctx.new_page()
    login(page)
    all_notes = {}
    for slug, route, label in ROUTES:
        d = os.path.join(SHOTS, slug)
        os.makedirs(os.path.abspath(d), exist_ok=True)
        try:
            page.goto(os.getenv("GUIDE_BASE", "http://localhost:5173") + route,
                      wait_until="networkidle", timeout=20000)
        except Exception as e:
            print(f"[WARN] {slug} nav: {e}")
        page.wait_for_timeout(1600)
        path = os.path.join(os.path.abspath(d), "00-base.png")
        page.screenshot(path=path, full_page=True)
        try:
            inv = page.evaluate(INVENTORY_JS)
        except Exception as e:
            inv = {"error": str(e)}
        inv["_route"] = route
        inv["_label"] = label
        inv["_shot"] = f"docs/screenshots/guide/{slug}/00-base.png"
        all_notes[slug] = inv
        nb = len(inv.get("buttons", []))
        ni = len(inv.get("inputs", []))
        ns = len(inv.get("selects", []))
        nt = len(inv.get("tabs", []))
        print(f"[OK] {slug:18s} btn={nb:2d} input={ni:2d} select={ns} tab={nt}  -> {path}")

    # write JSON
    jpath = os.path.abspath(os.path.join(SHOTS, "..", "..", ".guide-notes.json"))
    with open(jpath, "w") as f:
        json.dump(all_notes, f, indent=2, ensure_ascii=False)
    # write readable markdown
    mpath = os.path.abspath(os.path.join(SHOTS, "..", "..", ".guide-notes.md"))
    with open(mpath, "w") as f:
        f.write("# DPMBG Guide — Element Inventory (Fase 1)\n\n")
        f.write("Auto-dumped via `tools/guide/explore.py` (login platform_admin, base state).\n\n")
        for slug, route, label in ROUTES:
            inv = all_notes.get(slug, {})
            f.write(f"## {label}  `{route}`  (`{slug}`)\n\n")
            f.write(f"![base](screenshots/guide/{slug}/00-base.png)\n\n")
            if inv.get("headings"):
                f.write("**Headings:** " + " · ".join(inv["headings"]) + "\n\n")
            if inv.get("tabs"):
                f.write("**Tabs:** " + " | ".join(inv["tabs"]) + "\n\n")
            if inv.get("buttons"):
                f.write("**Buttons:** " + " · ".join(f"`{x}`" for x in inv["buttons"]) + "\n\n")
            if inv.get("inputs"):
                rows = [f"{i['type']} `{i['name']}` _{i['placeholder']}_" for i in inv["inputs"]]
                f.write("**Inputs:** " + " · ".join(rows) + "\n\n")
            if inv.get("selects"):
                for s in inv["selects"]:
                    f.write(f"**Select** `{s['name']}`: {', '.join(s['options'])}\n\n")
            f.write("---\n\n")
    print("\nJSON ->", jpath)
    print("MD   ->", mpath)
    ctx.close(); b.close(); p.stop()


if __name__ == "__main__":
    main()

"""End-to-end browser test: drives every user-facing flow of Mineral Scout
against a live server (default http://localhost:8106) with real upstreams.

Run:  .venv/bin/python scripts/e2e_browser.py
Needs: pip install playwright (chromium already cached), server running.

Covers: config/datalist, MRDS sites + commodity filter chips, named-variety
search (Kentucky agate) with region card + fly-to, site detail drawer
("What's here" mineral list), land-status drawer (public + private + owner
links), abandoned mines + tailings toggle, active claims, ownership overlay
+ legend, laws modal (AZ correction + KY), bookmarks add/remove, GPX export,
mindat disabled message, all-statuses-unchecked guard, place search (soft —
external Nominatim), console-error sweep.
"""
import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("MSCOUT_E2E_BASE", "http://localhost:8106")
SHOT = os.environ.get("MSCOUT_E2E_SHOT", "/tmp/mineral-scout-e2e.png")
failures: list[str] = []
warnings: list[str] = []
console_errors: list[str] = []


def check(name, fn, soft=False):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as exc:
        msg = str(exc).splitlines()[0][:160]
        if soft:
            warnings.append(name)
            print(f"WARN {name}: {msg}")
        else:
            failures.append(name)
            print(f"FAIL {name}: {msg}")


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.goto(BASE, wait_until="domcontentloaded")

    # -- boot / config
    check("title", lambda: expect(page).to_have_title(re.compile("Mineral Scout")))
    check("sidebar renders", lambda: expect(page.locator("#sidebar h1")).to_contain_text("Mineral Scout"))
    page.wait_for_timeout(2500)
    check("datalist has commodities + varieties", lambda: assert_true(
        page.locator("#commodity-list option").count() > 30
        and page.locator('#commodity-list option[value="Kentucky agate"]').count() == 1,
        f"options={page.locator('#commodity-list option').count()}"))

    # -- sites over default AZ view
    check("sites loaded", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile(r"\d+ mineral sites"), timeout=60000))

    # -- commodity chip filter
    page.fill("#commodity-input", "Gold")
    page.dispatch_event("#commodity-input", "change")
    check("gold chip added", lambda: expect(page.locator(".chip")).to_contain_text("Gold"))
    check("gold filter applied", lambda: expect(page.locator("#status-line")).to_contain_text(
        "Filter: Gold", timeout=60000))
    page.locator(".chip").first.click()  # remove chip
    check("chip removed", lambda: assert_true(page.locator(".chip").count() == 0, "chip still present"))

    # -- named-variety search: Kentucky agate
    page.fill("#commodity-input", "kentucky agate")
    page.dispatch_event("#commodity-input", "change")
    check("variety chip added", lambda: expect(page.locator(".chip")).to_contain_text(
        re.compile("kentucky agate", re.I)))
    check("variety card shows region + legal note", lambda: expect(
        page.locator(".variety-card")).to_contain_text("Knobs region", timeout=10000))
    before = page.evaluate("map.getCenter().lng")
    page.locator(".variety-card button").click()
    page.wait_for_timeout(1500)
    check("go-to-region flies to Kentucky", lambda: assert_true(
        abs(page.evaluate("map.getCenter().lng") - (-83.9)) < 1.5
        and abs(page.evaluate("map.getCenter().lat") - 37.6) < 1.0,
        f"center={page.evaluate('map.getCenter()')} (was lng={before})"))
    check("variety warning surfaced", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile("Kentucky agate.*searched as", re.I), timeout=60000), soft=True)
    page.locator(".chip").first.click()  # clear variety chip

    # -- site detail drawer ("What's here")
    # open a site popup deterministically: markers near the viewport edge are
    # unclickable and moveend reloads swap the layer set, so drive Leaflet directly
    def open_site_popup():
        page.evaluate("const l0 = sitesCluster.getLayers()[0]; map.setView(l0.getLatLng(), 15);")
        page.wait_for_timeout(3500)  # let the moveend reload settle
        page.evaluate("sitesCluster.getLayers()[0].openPopup()")
        page.wait_for_timeout(600)

    page.evaluate("map.setView([33.65947, -112.03653], 14)")  # Webb Group (AU), AZ
    page.wait_for_timeout(4000)
    open_site_popup()
    check("site popup shows mineral names", lambda: expect(
        page.locator(".leaflet-popup")).to_contain_text("Minerals:", timeout=15000))
    page.locator(".leaflet-popup button", has_text="What's here").click()
    check("detail drawer lists minerals at location", lambda: expect(
        page.locator("#detail")).to_contain_text("Minerals / commodities here", timeout=60000))
    check("detail drawer has USGS record link", lambda: expect(
        page.locator("#detail a[href*='mrdata.usgs.gov']")).to_be_visible(timeout=10000))
    page.click("#detail-close")

    # -- bookmarks add/remove
    open_site_popup()
    page.locator(".leaflet-popup button", has_text="Bookmark").click()
    check("bookmark count increments", lambda: expect(page.locator("#bm-count")).to_have_text("1"))
    page.click("#btn-bookmarks")
    check("bookmark listed in modal", lambda: expect(page.locator("#modal-body button", has_text="remove").first).to_be_visible(timeout=10000))
    page.locator("#modal-body button", has_text="remove").first.click()
    check("bookmark removed", lambda: expect(page.locator("#bm-count")).to_have_text("0"))
    page.click("#modal-close")

    # -- land status via popup button
    open_site_popup()
    page.locator(".leaflet-popup button", has_text="Land status").click()
    check("land-status drawer opens", lambda: expect(page.locator("#detail h2")).to_contain_text(
        "Land status", timeout=90000))
    check("land-status verdict badge", lambda: expect(page.locator("#detail .badge").first).to_be_visible(timeout=90000))
    page.click("#detail-close")

    # -- check-land mode on a known PRIVATE suburban point -> owner flow
    page.evaluate("map.setView([33.6112, -112.3405], 15)")
    page.click("#btn-check-land")
    page.click("#map", position={"x": 700, "y": 450})
    check("private point shows owner lookup", lambda: expect(page.locator("#detail")).to_contain_text(
        re.compile("Find & ask the owner|owner", re.I), timeout=90000))
    check("assessor link present", lambda: expect(
        page.locator("#detail a[href*='maricopa']").first).to_be_visible(timeout=10000), soft=True)
    page.click("#btn-check-land")  # mode off
    page.click("#detail-close")

    # -- abandoned mines + tailings toggle (Globe-Miami district)
    page.evaluate("map.setView([33.4, -110.8], 11)")
    page.check("#layer-mines")
    check("mine features loaded", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile(r"\d+ mine features"), timeout=60000))
    page.check("#mines-tailings-only")
    check("tailings-only loads tailings/dumps", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile(r"\d+ mine features"), timeout=60000))
    page.uncheck("#mines-tailings-only")
    page.uncheck("#layer-mines")

    # -- active claims (needs z>=8)
    page.evaluate("map.setView([34.5, -113.45], 11)")
    page.check("#layer-claims")
    check("active claims loaded", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile(r"\d+ active claims"), timeout=90000))
    page.uncheck("#layer-claims")

    # -- ownership overlay
    page.check("#layer-ownership")
    check("ownership legend visible", lambda: expect(page.locator("#ownership-legend")).to_be_visible())
    page.uncheck("#layer-ownership")

    # -- laws modal
    page.click("#btn-laws")
    check("laws modal lists states", lambda: expect(page.locator("#modal-body")).to_contain_text(
        "Arizona", timeout=30000))
    page.locator("#modal-body button", has_text="AZ").click()
    check("AZ trust-land correction shown", lambda: expect(page.locator("#modal-body")).to_contain_text(
        "NOT open to rockhounding", timeout=30000))
    page.click("#modal-close")
    page.click("#btn-laws")
    page.locator("#modal-body button", has_text="KY").click()
    check("KY law panel shown", lambda: expect(page.locator("#modal-body")).to_contain_text(
        "Kentucky", timeout=30000))
    page.click("#modal-close")

    # -- GPX export endpoint (from page context, current view params)
    gpx = page.evaluate("""async () => {
      const b = map.getBounds();
      const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(3)).join(',');
      const r = await fetch(`/api/export.gpx?bbox=${bbox}`);
      return { status: r.status, body: (await r.text()).slice(0, 200) };
    }""")
    check("GPX export returns gpx xml", lambda: assert_true(
        gpx["status"] == 200 and gpx["body"].startswith("<?xml") and "<gpx" in gpx["body"],
        f"status={gpx['status']} body={gpx['body'][:80]}"))

    # -- mindat disabled message (no API key on this box)
    # the app immediately unchecks the box when the key is missing, so
    # page.check() would report "state didn't change" — fire the event directly
    page.evaluate("""() => {
      const cb = document.getElementById('layer-mindat');
      cb.checked = true;
      cb.dispatchEvent(new Event('change'));
    }""")
    check("mindat explains missing key", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile("mindat", re.I), timeout=15000))

    # -- all statuses unchecked -> explicit message, no sites
    for cb in page.locator("#status-filters input").all():
        cb.uncheck()
    check("all-unchecked shows guard message", lambda: expect(page.locator("#status-line")).to_contain_text(
        "All development statuses unchecked", timeout=15000))
    for cb in page.locator("#status-filters input").all():
        cb.check()

    # -- place search (external Nominatim — soft check)
    page.fill("#place-search", "Quartzsite, AZ")
    page.click("#place-go")
    check("place search moves map", lambda: expect(page.locator("#status-line")).to_contain_text(
        re.compile("Moved to", re.I), timeout=20000), soft=True)

    page.screenshot(path=SHOT, full_page=False)
    browser.close()

real_errors = [e for e in console_errors
               if "tile" not in e.lower() and "favicon" not in e.lower()
               and "unpkg" not in e.lower() and "nominatim" not in e.lower()
               and "403" not in e and "404 (Not Found)" not in e
               and "503" not in e]  # mindat layer intentionally 503s without a key
if real_errors:
    print("CONSOLE ERRORS:")
    for e in real_errors[:10]:
        print("  ", e[:200])
    failures.append("console errors")

print(f"\n{len(failures)} failures, {len(warnings)} soft warnings")
print("ALL PASS" if not failures else "FAILURES: " + ", ".join(failures))
sys.exit(1 if failures else 0)

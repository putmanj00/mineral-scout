"""Named mineral varieties — the names collectors actually search for.

MRDS indexes generic commodities (GEM, SIL, F...), not collector names like
"Kentucky agate". Many famous varieties are collected from creek gravels or
fee digs that have no MRDS mine record at all, so each entry carries its
classic REGION and an honest collecting note; the UI flies to the region and
applies the base-commodity filter instead of pretending a code search covers
it.

Regions/blurbs verified against well-established rockhounding localities;
legal notes are conservative — land status still rules (use the app's
check-land tool).
"""
import re

# bbox = [west, south, east, north]
VARIETIES = [
    {
        "name": "Kentucky agate",
        "aliases": ["ky agate", "kentucky blue agate"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Knobs region, east-central Kentucky", "bbox": [-84.5, 37.2, -83.3, 38.0]},
        "blurb": ("Kentucky's state rock: red/black banded agate weathering out of the "
                  "Borden Formation, collected from creek gravels and road cuts in "
                  "Estill, Powell, Jackson, Rockcastle and Madison counties."),
        "note": ("Almost all productive ground is PRIVATE farmland — owner permission is "
                 "the whole game (use the land-status tool). State nature preserves are "
                 "off-limits. MRDS has almost no records for gravel collecting like this."),
    },
    {
        "name": "Holley blue agate",
        "aliases": ["holly blue agate", "holy blue agate", "holley blue", "holly blue"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Holley / Sweet Home area, Linn County, Oregon", "bbox": [-122.95, 44.25, -122.55, 44.5]},
        "blurb": ("Lavender-blue chalcedony/agate from the Holley area near Sweet Home, "
                  "Oregon — prized for cutting; found in road cuts, the Calapooia River "
                  "gravels, and surrounding hills."),
        "note": ("Classic digging grounds are largely private timber company land — "
                 "permission or organized club digs. River gravel bars below high-water "
                 "line are the usual public-ish access; check current OR rules."),
    },
    {
        "name": "Fire agate",
        "aliases": [],
        "codes": ["GEM", "SIL"],
        "region": {"label": "SE Arizona BLM rockhound areas (Round Mountain, Black Hills)", "bbox": [-110.4, 32.5, -108.9, 33.3]},
        "blurb": ("Iridescent chalcedony. BLM maintains free designated collecting areas: "
                  "Round Mountain Rockhound Area (near Duncan) and Black Hills Rockhound "
                  "Area (near Safford)."),
        "note": "Free casual collecting inside the designated areas, hand tools only.",
    },
    {
        "name": "Fairburn agate",
        "aliases": [],
        "codes": ["GEM"],
        "region": {"label": "Fairburn area / Buffalo Gap National Grassland, South Dakota", "bbox": [-103.6, 43.3, -102.4, 43.9]},
        "blurb": ("South Dakota's state gemstone, hunted on the gravel beds east of the "
                  "Black Hills around Fairburn and across Buffalo Gap National Grassland."),
        "note": ("Hobby collecting is allowed on the National Grassland (hand methods); "
                 "Badlands National Park is strictly off-limits."),
    },
    {
        "name": "Lake Superior agate",
        "aliases": ["laker agate", "lakers"],
        "codes": ["GEM"],
        "region": {"label": "Lake Superior shores + glacial gravels (MN/WI/MI)", "bbox": [-94.0, 45.8, -89.5, 48.3]},
        "blurb": ("Minnesota's state gemstone, spread by glaciers across MN/WI/MI — "
                  "beaches, rivers, and gravel pits."),
        "note": ("Beaches below high-water line are generally fair game in small amounts; "
                 "gravel pits need the operator's permission. State parks vary — check."),
    },
    {
        "name": "Montana agate",
        "aliases": ["yellowstone agate"],
        "codes": ["GEM"],
        "region": {"label": "Yellowstone River gravels, eastern Montana", "bbox": [-107.0, 45.4, -104.0, 47.8]},
        "blurb": ("Dendritic agate from Yellowstone River gravel bars, roughly Custer to "
                  "Sidney — classic float hunting."),
        "note": ("Use public fishing-access sites and gravel bars; riverbank above the "
                 "high-water line is often private ranch land — ask."),
    },
    {
        "name": "Oregon sunstone",
        "aliases": ["sunstone"],
        "codes": ["GEM"],
        "region": {"label": "BLM Sunstone Public Collection Area, north of Plush, Oregon", "bbox": [-119.95, 42.55, -119.55, 42.85]},
        "blurb": ("Copper-schiller labradorite, Oregon's state gemstone. BLM's free "
                  "Sunstone Public Collection Area sits north of Plush, Lake County."),
        "note": ("Free collecting inside the public area; the surrounding better ground "
                 "is covered by active claims and fee mines (Dust Devil, Spectrum) — "
                 "check the Claims layer."),
    },
    {
        "name": "Thunderegg",
        "aliases": ["thundereggs", "thunder egg"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Madras / Ochoco area, central Oregon", "bbox": [-121.3, 44.0, -120.3, 44.9]},
        "blurb": ("Oregon's state rock. Famous Priday beds near Madras (Richardson Rock "
                  "Ranch, fee dig) plus free USFS sites in the Ochoco NF (e.g. White Fir "
                  "Springs)."),
        "note": "Best beds are fee digs on private ranch land; USFS sites allow hobby digging — check the district.",
    },
    {
        "name": "Obsidian",
        "aliases": ["glass buttes obsidian", "rainbow obsidian", "mahogany obsidian"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Glass Buttes, central Oregon (BLM)", "bbox": [-120.2, 43.3, -119.7, 43.65]},
        "blurb": ("Glass Buttes: square miles of free BLM collecting for rainbow, "
                  "mahogany, silver-sheen and other obsidian varieties."),
        "note": "Free casual collecting (hand tools); a few small active claims exist — check the Claims layer.",
    },
    {
        "name": "Herkimer diamond",
        "aliases": ["herkimer", "herkimer diamonds"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Herkimer / Middleville, Mohawk Valley, New York", "bbox": [-75.15, 42.85, -74.55, 43.25]},
        "blurb": ("Doubly-terminated quartz crystals from Little Falls Dolostone vugs, "
                  "Mohawk Valley NY."),
        "note": ("Essentially all collecting is at private fee mines (Herkimer Diamond "
                 "Mines, Ace of Diamonds) — no public digging."),
    },
    {
        "name": "Fluorite (KY–IL Fluorspar District)",
        "aliases": ["kentucky fluorite", "illinois fluorite", "cave-in-rock fluorite", "fluorspar"],
        "codes": ["F"],
        "region": {"label": "Western KY / SE Illinois Fluorspar District", "bbox": [-88.7, 37.0, -88.0, 37.6]},
        "blurb": ("The classic KY–IL Fluorspar District (Crittenden/Livingston counties KY, "
                  "Cave-in-Rock IL): world-famous purple/yellow fluorite. MRDS is dense "
                  "with real mine records here."),
        "note": ("Historic mines are on private land and mostly reclaimed/flooded — "
                 "permission required; the Ben E. Clement Mineral Museum (Marion, KY) "
                 "runs organized fee digs on old mine dumps."),
    },
    {
        "name": "Keokuk geode",
        "aliases": ["keokuk geodes", "geode", "geodes"],
        "codes": ["GEM", "SIL"],
        "region": {"label": "Keokuk tri-state area (IA/IL/MO), Warsaw Formation", "bbox": [-91.9, 40.2, -91.1, 40.8]},
        "blurb": ("Quartz-lined geodes from the Warsaw Formation around Keokuk IA, "
                  "Hamilton IL, and Alexandria MO."),
        "note": ("Productive creek exposures are on private farms — several run fee digs; "
                 "Geode State Park (IA) prohibits collecting."),
    },
    {
        "name": "Arkansas quartz",
        "aliases": ["mount ida quartz", "hot springs quartz", "quartz crystal"],
        "codes": ["SIL", "GEM"],
        "region": {"label": "Ouachita Mountains — Mount Ida / Jessieville, Arkansas", "bbox": [-94.0, 34.3, -92.9, 34.9]},
        "blurb": ("The Ouachitas around Mount Ida are the US quartz-crystal capital; "
                  "dozens of MRDS records plus commercial mines."),
        "note": ("Best access is fee digs (multiple mines around Mount Ida); much of the "
                 "rest is active claims or Ouachita NF with hobby rules — check locally."),
    },
    {
        "name": "Star garnet",
        "aliases": ["idaho star garnet"],
        "codes": ["GEM"],
        "region": {"label": "Emerald Creek, near St. Maries, Idaho (USFS fee area)", "bbox": [-116.5, 46.9, -116.2, 47.1]},
        "blurb": ("Idaho's state gem: 4- and 6-ray star almandine garnets. The USFS "
                  "Emerald Creek Garnet Area sells daily dig permits in season."),
        "note": "Fee/permit dig only, seasonal (typically Memorial Day–Labor Day); no freelance digging.",
    },
    {
        "name": "Turquoise",
        "aliases": [],
        "codes": ["GEM"],
        "region": {"label": "Central Nevada turquoise belt", "bbox": [-118.0, 37.8, -116.5, 39.5]},
        "blurb": ("Most famous US turquoise (Royston, Candelaria, Kingman AZ) comes from "
                  "ACTIVE private claims/mines."),
        "note": ("Collecting on someone's turquoise claim is theft of the claimed mineral "
                 "— use fee digs (e.g. Royston tours) or buy rough. Check the Claims layer."),
    },
    {
        "name": "Petrified wood",
        "aliases": ["petrified forest wood"],
        "codes": ["GEM", "SIL"],
        "region": None,  # widespread across the West — no single classic bbox
        "blurb": ("Widespread on BLM land across the West (notable areas in AZ, UT, WY, "
                  "OR). Federal free-use limits: 25 lb/day plus one piece, 250 lb/yr "
                  "(43 CFR 3622)."),
        "note": "Petrified Forest National Park is absolutely off-limits; sale of free-use wood is illegal.",
    },
    {
        "name": "Diamonds (Crater of Diamonds)",
        "aliases": ["crater of diamonds", "arkansas diamonds", "diamond"],
        "codes": ["GEM"],
        "region": {"label": "Crater of Diamonds State Park, Murfreesboro, Arkansas", "bbox": [-93.75, 34.0, -93.6, 34.12]},
        "blurb": ("The only public diamond dig in the US: a plowed volcanic pipe at "
                  "Crater of Diamonds State Park — pay the day fee, keep what you find."),
        "note": "Fee park with rules on tools; everything you find is yours, including diamonds.",
    },
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", s.lower())).strip()


_INDEX: dict[str, dict] = {}
for v in VARIETIES:
    _INDEX[_norm(v["name"])] = v
    for a in v["aliases"]:
        _INDEX[_norm(a)] = v


def resolve(name: str) -> dict | None:
    """Exact normalized name/alias match; forgiving about case/punctuation."""
    return _INDEX.get(_norm(name))


def public_list() -> list[dict]:
    return [{
        "name": v["name"],
        "aliases": v["aliases"],
        "codes": v["codes"],
        "region": v["region"],
        "blurb": v["blurb"],
        "note": v["note"],
    } for v in VARIETIES]

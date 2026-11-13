"""Per-state mineral-collecting law summaries served to the UI law panel.

Informational only, not legal advice. Verified against primary sources
(CFR via Cornell LII, agency pages) on 2026-07-12; rules change — the UI
shows the verified date and a "confirm before you dig" banner with every
summary. Items below marked 'check locally' were not confirmed against a
primary source and are flagged as such to the user.
"""

DISCLAIMER = (
    "Informational only — not legal advice. Rules change and many areas carry "
    "special designations (wilderness, national monuments, ACECs, active "
    "claims, tribal land) that override the general rule. Confirm with the "
    "managing agency before you dig."
)

SAFETY_BANNER = (
    "Abandoned mines are deadly: unstable shafts, bad air, hidden winzes, "
    "explosives, water-filled workings. MSHA's 'Stay Out — Stay Alive' rule: "
    "never enter an abandoned mine. Collect on surface dumps/tailings only "
    "where legal. In Arizona, report open mine hazards to the AZ State Mine "
    "Inspector, (602) 542-5971."
)

FEDERAL = {
    "blm_casual": {
        "title": "BLM land — casual collecting",
        "summary": (
            "On most BLM public land you may collect reasonable amounts of rocks, "
            "mineral specimens, and semiprecious gemstones for noncommercial use, "
            "free and without a permit, except in developed recreation sites and "
            "posted closures (43 CFR 8365.1-5(b)). Hand tools only — no explosives "
            "or motorized equipment. Petrified wood: 25 lb/day plus one piece, max "
            "250 lb/yr (43 CFR 3622.4); several BLM states (incl. AZ) apply the "
            "same 25/250 numbers to all specimen collecting. Selling what you "
            "collect requires a BLM contract. NOT allowed for the claimed mineral "
            "on someone's active mining claim — check the Claims layer first. BLM "
            "national monuments and many special-designation areas are closed."
        ),
        "citations": [
            "https://www.law.cornell.edu/cfr/text/43/8365.1-5",
            "https://www.law.cornell.edu/cfr/text/43/3622.4",
            "https://www.blm.gov/programs/recreation/rockhounding",
        ],
    },
    "usfs_hobby": {
        "title": "National Forest land — hobby collecting",
        "summary": (
            "Forest Service policy allows collecting small amounts of widespread, "
            "low-value common rocks and minerals, plus recreational gold panning, "
            "for personal noncommercial use without a permit — surface collection "
            "with no significant ground disturbance. There is no single CFR "
            "granting this right: significant digging falls under the 36 CFR 228 "
            "operations rules, and individual forests vary (some require a free "
            "permit) — check the ranger district."
        ),
        "citations": [
            "https://www.fs.usda.gov/r08/gwj/forest-products/recreation-mineral-collecting",
            "https://www.law.cornell.edu/cfr/text/36/part-228",
        ],
    },
    "nps_prohibited": {
        "title": "National Parks — prohibited",
        "summary": (
            "NPS units prohibit possessing, destroying, removing, digging, or "
            "disturbing mineral resources, and ban metal detectors (36 CFR 2.1). "
            "No rockhounding, period — including Grand Canyon and Petrified "
            "Forest. Tribal land is closed without tribal government permission."
        ),
        "citations": ["https://www.law.cornell.edu/cfr/text/36/2.1"],
    },
}

STATES = {
    "AZ": {
        "name": "Arizona",
        "posture": "friendly",
        "headline": (
            "Top rockhounding state — but via its huge BLM acreage, NOT via State "
            "Trust land. The common belief that the $15 recreational permit lets "
            "you dig on Trust land is wrong."
        ),
        "rules": [
            {
                "title": "BLM land in Arizona — where you CAN dig",
                "summary": (
                    "BLM Arizona's rockhounding rules: up to 25 lb/day, 250 lb/yr of "
                    "mineral specimens, rock, semiprecious gemstones, common "
                    "invertebrate fossils, and petrified wood, for personal "
                    "noncommercial use. Hand tools only. Meteorites max 10 lb/yr, "
                    "surface finds. Recreational gold panning OK; suction dredging "
                    "is NOT casual use (needs a 43 CFR 3809 notice/plan). Off "
                    "limits: BLM national monuments, ACECs, active claims (for the "
                    "claimed mineral), artifacts/arrowheads, vertebrate fossils. "
                    "Metal detecting OK except San Pedro Riparian NCA."
                ),
                "citations": [
                    "https://www.blm.gov/sites/default/files/documents/files/2014%20Rockhounding_14_web_2018.pdf",
                    "https://www.law.cornell.edu/cfr/text/43/8365.1-5",
                ],
            },
            {
                "title": "Arizona State Trust land — NOT open to rockhounding",
                "summary": (
                    "State Trust land is not public land. The recreational permit "
                    "($15/yr individual, $20 family) covers hiking, camping ≤14 "
                    "days/yr, and similar — ASLD's activity list does NOT include "
                    "rockhounding, and BLM Arizona's pamphlet states flatly: "
                    "'Rockhounding and metal detecting are not allowed on Arizona "
                    "State Trust Land.' Entering without a permit (or collecting "
                    "outside its terms) is criminal trespass (A.R.S. 37-501). The "
                    "lawful path to minerals on Trust land is an ASLD Mineral "
                    "Exploration Permit ($500) or a Title 27 lease — commercial "
                    "instruments, not hobby permits. Check parcels in the ASLD "
                    "viewer: gis.azland.gov."
                ),
                "citations": [
                    "https://land.az.gov/faqs",
                    "https://land.az.gov/applications-permits",
                ],
            },
        ],
        "agency": {"name": "Arizona State Land Department", "url": "https://land.az.gov"},
    },
    "NV": {
        "name": "Nevada",
        "posture": "friendly",
        "headline": "Mostly BLM land — federal casual-collecting rules apply across huge open areas; state trust land is negligible.",
        "rules": [],
        "agency": {"name": "Nevada Division of Minerals", "url": "https://minerals.nv.gov"},
    },
    "CA": {
        "name": "California",
        "posture": "restrictive-lean",
        "headline": "BLM casual collecting OK; State Parks prohibit collecting; suction dredging heavily restricted statewide.",
        "rules": [],
        "agency": {"name": "California State Parks / BLM CA", "url": "https://www.blm.gov/california"},
    },
    "UT": {
        "name": "Utah",
        "posture": "friendly",
        "headline": "BLM: 25 lb/day + one piece, 250 lb/yr. State trust (SITLA) land needs a paid annual rockhounding permit with the same limits (per Utah Geological Survey).",
        "rules": [],
        "agency": {"name": "Utah Geological Survey collecting rules", "url": "https://geology.utah.gov/popular/rocks-minerals/collecting-rules/"},
    },
    "CO": {
        "name": "Colorado",
        "posture": "mixed",
        "headline": "BLM/USFS casual rules apply; State Land Board trust land is generally closed to recreation without authorization (check locally).",
        "rules": [],
        "agency": {"name": "Colorado State Land Board", "url": "https://slb.colorado.gov"},
    },
    "NM": {
        "name": "New Mexico",
        "posture": "mixed",
        "headline": "Federal land per BLM rules; State Trust land needs a $35/yr recreational access permit and it does NOT authorize mineral removal.",
        "rules": [],
        "agency": {"name": "NM State Land Office", "url": "https://www.nmstatelands.org/outdoorrecreation/"},
    },
    "OR": {
        "name": "Oregon",
        "posture": "friendly",
        "headline": "Strong BLM rockhounding culture (Glass Butte obsidian, sunstones — watch for claims); small-amount ocean-beach agate collecting allowed (check current OPRD limits).",
        "rules": [],
        "agency": {"name": "Oregon DOGAMI", "url": "https://www.oregon.gov/dogami/learnmore/pages/fossilsmineralsgems.aspx"},
    },
    "ID": {
        "name": "Idaho",
        "posture": "friendly",
        "headline": "BLM/USFS casual rules; state endowment land posture varies — check Idaho Dept of Lands. Star garnets at Emerald Creek (USFS fee site).",
        "rules": [],
        "agency": {"name": "Idaho Dept of Lands", "url": "https://idl.idaho.gov"},
    },
    "MT": {
        "name": "Montana",
        "posture": "mixed",
        "headline": "Federal land per BLM rules; state trust land needs a DNRC recreational-use license and it doesn't convey mineral rights — check before collecting.",
        "rules": [],
        "agency": {"name": "Montana DNRC trust lands", "url": "https://dnrc.mt.gov/trustland/public-use/"},
    },
    "WY": {
        "name": "Wyoming",
        "posture": "friendly",
        "headline": "Nearly all BLM land open per federal limits; petrified wood 25 lb/day capped 250 lb/yr; state trust land needs OSLI authorization (check locally).",
        "rules": [],
        "agency": {"name": "Wyoming State Geological Survey", "url": "https://www.wsgs.wyo.gov"},
    },
    "KY": {
        "name": "Kentucky",
        "posture": "restrictive",
        "headline": (
            "No BLM public domain; almost all land private — owner permission is "
            "the path. USFS hobby rules apply in Daniel Boone NF (check district). "
            "Watch for severed mineral estates: the surface owner may not own the "
            "minerals."
        ),
        "rules": [],
        "agency": {"name": "Kentucky Geological Survey", "url": "https://www.uky.edu/KGS"},
    },
}

TRESPASS_NOTE = (
    "On private land you need the owner's permission — entering without it is "
    "trespass in every state, and minerals belong to the owner (or a severed "
    "mineral-rights holder, common in coal states). Use the parcel lookup to "
    "find the assessor-record owner, then ask in writing; many owners say yes "
    "to hobby collectors who offer to share finds and sign a liability waiver."
)


def get_state(code: str) -> dict | None:
    state = STATES.get(code.upper())
    if not state:
        return None
    return {
        **state,
        "federal": FEDERAL,
        "disclaimer": DISCLAIMER,
        "safety": SAFETY_BANNER,
        "trespass": TRESPASS_NOTE,
        "verified": "2026-07-12",
    }


def list_states() -> list[dict]:
    return [{"code": code, "name": s["name"], "posture": s["posture"], "headline": s["headline"]}
            for code, s in sorted(STATES.items())]

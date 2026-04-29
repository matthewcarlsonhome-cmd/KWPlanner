"""Match type recommendation engine for imported search terms.

Analyzes search term performance data and recommends EXACT, PHRASE, SKIP,
or NEGATIVE match types based on conversion data, CTR, word count,
location signals, and commercial intent.
"""

from typing import Tuple

US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
]

US_CITIES = [
    "houston", "dallas", "austin", "san antonio", "fort worth",
    "phoenix", "tucson", "scottsdale", "mesa", "chandler", "gilbert",
    "los angeles", "san diego", "san francisco", "sacramento", "san jose",
    "miami", "tampa", "orlando", "jacksonville", "naples", "sarasota",
    "fort lauderdale", "west palm beach", "boca raton", "st petersburg",
    "atlanta", "savannah", "charlotte", "raleigh", "durham",
    "nashville", "memphis", "knoxville", "chattanooga",
    "las vegas", "henderson", "reno",
    "denver", "colorado springs", "boulder",
    "chicago", "springfield", "naperville",
    "new york", "brooklyn", "manhattan",
    "seattle", "portland", "boise",
    "detroit", "grand rapids", "ann arbor",
    "minneapolis", "st paul",
    "boston", "worcester", "cambridge",
    "philadelphia", "pittsburgh",
    "baltimore", "annapolis",
    "richmond", "virginia beach", "norfolk",
    "oklahoma city", "tulsa",
    "omaha", "lincoln",
    "kansas city", "st louis",
    "indianapolis", "columbus", "cleveland", "cincinnati",
    "milwaukee", "madison",
    "albuquerque", "santa fe",
    "salt lake city", "provo",
    "honolulu", "anchorage",
]

LOCATION_SIGNALS = [
    "near me", "nearby", "in my area", "local", "closest",
    "around me", "in the area", "next to me",
]

COMMERCIAL_INTENT_SIGNALS = [
    "cost", "price", "pricing", "quote", "estimate", "hire",
    "buy", "purchase", "deal", "sale", "discount", "financing",
    "near me", "company", "contractor", "service", "install",
    "installation", "builder", "repair", "remodel", "renovation",
    "replace", "replacement", "professional", "licensed", "insured",
    "best", "top rated", "reviews", "rated", "affordable",
]


def contains_location_signal(search_term: str) -> bool:
    """Check if search term contains location-related signals."""
    st_lower = search_term.lower()

    for signal in LOCATION_SIGNALS:
        if signal in st_lower:
            return True

    for state in US_STATES:
        if f" {state}" in f" {st_lower}" or f" {state} " in f" {st_lower} ":
            return True

    for city in US_CITIES:
        if f" {city}" in f" {st_lower}" or f" {city} " in f" {st_lower} ":
            return True

    # Pattern: "in [city/state]" at end of query
    words = st_lower.split()
    if len(words) >= 3 and words[-2] == "in":
        return True

    return False


def contains_commercial_intent(search_term: str) -> bool:
    """Check if search term contains commercial intent signals."""
    st_lower = search_term.lower()
    for signal in COMMERCIAL_INTENT_SIGNALS:
        if signal in st_lower:
            return True
    return False


def recommend_match_type(
    search_term: str,
    clicks: int = 0,
    conversions: float = 0,
    conv_rate: float = 0,
    ctr: float = 0,
    impressions: int = 0,
) -> Tuple[str, str]:
    """
    Recommend match type for a search term based on performance data.

    Returns (match_type, reason) where match_type is one of:
    EXACT, PHRASE, SKIP, NEGATIVE
    """
    word_count = len(search_term.split())
    has_location = contains_location_signal(search_term)
    has_commercial = contains_commercial_intent(search_term)

    # Rule 1: Converting search terms -> EXACT
    if conversions >= 1:
        return "EXACT", "Converting query — lock in exact match"

    # Rule 2: High CTR + enough data
    if clicks >= 10 and ctr >= 0.03:
        if word_count >= 3 or has_location or has_commercial:
            return "EXACT", "High CTR + specific intent"
        return "PHRASE", "High CTR but broad — phrase captures variants"

    # Rule 3: Long-tail with commercial intent
    if word_count >= 4 and has_commercial:
        return "EXACT", "Long-tail commercial intent"

    # Rule 4: Location-based queries
    if has_location and word_count >= 3:
        return "EXACT", "Location-specific query"

    # Rule 5: Moderate data, generic
    if clicks >= 5:
        return "PHRASE", "Moderate data — phrase to gather more signal"

    # Rule 6: Low data + generic
    if word_count <= 2 and clicks < 5:
        return "SKIP", "Too little data + too generic"

    return "PHRASE", "Default — phrase to gather data"

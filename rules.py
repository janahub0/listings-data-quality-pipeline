# The cleaning rules and the validation model. Kept in one file so the tests can import them.
import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# rough bounding box around Istanbul province. Anything outside is probably a wrong coordinate.
LAT_MIN, LAT_MAX = 40.7, 41.7
LON_MIN, LON_MAX = 27.9, 30.0

ROOM_TYPES = {"Entire home/apt", "Private room", "Shared room", "Hotel room"}

# Names written without Turkish letters -> proper spelling. Only these are mapped. Anything else is kept
# as it is and listed in the report, so nothing is changed without a rule.
DISTRICTS = {
    "adalar": "Adalar", "arnavutkoy": "Arnavutköy", "atasehir": "Ataşehir", "avcilar": "Avcılar",
    "bagcilar": "Bağcılar", "bahcelievler": "Bahçelievler", "bakirkoy": "Bakırköy",
    "basaksehir": "Başakşehir", "bayrampasa": "Bayrampaşa", "besiktas": "Beşiktaş", "beykoz": "Beykoz",
    "beylikduzu": "Beylikdüzü", "beyoglu": "Beyoğlu", "buyukcekmece": "Büyükçekmece",
    "catalca": "Çatalca", "cekmekoy": "Çekmeköy", "esenler": "Esenler", "esenyurt": "Esenyurt",
    "eyup": "Eyüpsultan", "eyupsultan": "Eyüpsultan", "fatih": "Fatih", "gaziosmanpasa": "Gaziosmanpaşa",
    "gungoren": "Güngören", "kadikoy": "Kadıköy", "kagithane": "Kağıthane", "kartal": "Kartal",
    "kucukcekmece": "Küçükçekmece", "maltepe": "Maltepe", "pendik": "Pendik", "sancaktepe": "Sancaktepe",
    "sariyer": "Sarıyer", "silivri": "Silivri", "sultanbeyli": "Sultanbeyli", "sultangazi": "Sultangazi",
    "sile": "Şile", "sisli": "Şişli", "tuzla": "Tuzla", "umraniye": "Ümraniye", "uskudar": "Üsküdar",
    "zeytinburnu": "Zeytinburnu",
}


def parse_price(text) -> Optional[float]:
    """'₺1,569.00' or '$ 120' -> 1569.0 or 120.0. Returns None when there is no number."""
    if text is None:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(text))
    if cleaned.count(".") > 1 or cleaned in ("", "."):
        return None
    return float(cleaned)


def _fold(name: str) -> str:
    """lower case, no accents, no spaces: 'Kadıköy ' -> 'kadikoy' (the Turkish dotless i is handled by hand)."""
    name = name.replace("İ", "i").replace("I", "i").replace("ı", "i")
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", name.lower())


def normalize_neighbourhood(raw) -> tuple[Optional[str], bool]:
    """Returns (clean name, was it found in the district list)."""
    if raw is None or str(raw).strip() == "":
        return None, False
    tidy = re.sub(r"\s+", " ", str(raw)).strip()
    key = _fold(tidy)
    if key in DISTRICTS:
        return DISTRICTS[key], True
    return tidy, False


def count_amenities(text) -> Optional[int]:
    """The amenities column is a list written as text, like ["Wifi", "Kitchen"]. Count the items."""
    if text is None or str(text).strip() in ("", "[]"):
        return None
    return len(re.findall(r'"[^"]+"', str(text)))


class Listing(BaseModel):
    """One listing after cleaning. Pydantic checks every row, a row that breaks a rule is rejected with the reason."""
    listing_id: int = Field(gt=0)
    neighbourhood: Optional[str] = None
    room_type: str
    price: float = Field(gt=0, le=1_000_000)
    accommodates: int = Field(ge=1, le=50)
    bedrooms: Optional[float] = Field(default=None, ge=0, le=50)
    beds: Optional[float] = Field(default=None, ge=0, le=50)
    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX)
    longitude: float = Field(ge=LON_MIN, le=LON_MAX)
    review_score: Optional[float] = Field(default=None, ge=0, le=5)

    @field_validator("room_type")
    @classmethod
    def known_room_type(cls, v):
        if v not in ROOM_TYPES:
            raise ValueError(f"unknown room type '{v}'")
        return v
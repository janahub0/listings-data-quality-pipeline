import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rules import Listing, count_amenities, normalize_neighbourhood, parse_price


def good_row(**changes):
    row = dict(listing_id=1, neighbourhood="Kadıköy", room_type="Entire home/apt", price=1500.0,
               accommodates=2, bedrooms=1, beds=1, latitude=41.0, longitude=29.0, review_score=4.5)
    row.update(changes)
    return row


def test_parse_price_symbols_and_commas():
    assert parse_price("₺1,569.00") == 1569.0
    assert parse_price("$ 120") == 120.0


def test_parse_price_no_number():
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("free") is None
    assert parse_price("1.2.3") is None


def test_neighbourhood_mapping():
    assert normalize_neighbourhood("Kadikoy") == ("Kadıköy", True)
    assert normalize_neighbourhood("  SISLI ") == ("Şişli", True)
    assert normalize_neighbourhood("Kadıköy") == ("Kadıköy", True)
    assert normalize_neighbourhood("Some New Place") == ("Some New Place", False)
    assert normalize_neighbourhood("") == (None, False)


def test_count_amenities():
    assert count_amenities('["Wifi", "Kitchen", "TV"]') == 3
    assert count_amenities("[]") is None
    assert count_amenities(None) is None


def test_good_row_passes():
    assert Listing(**good_row()).price == 1500.0


@pytest.mark.parametrize("changes", [
    dict(price=0),
    dict(price=-5),
    dict(price=5_000_000),
    dict(accommodates=0),
    dict(accommodates=99),
    dict(latitude=48.0),
    dict(longitude=10.0),
    dict(room_type="Castle"),
    dict(listing_id=0),
    dict(review_score=9),
])
def test_bad_rows_are_rejected(changes):
    with pytest.raises(ValidationError):
        Listing(**good_row(**changes))

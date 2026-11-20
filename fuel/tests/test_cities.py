import pytest

from fuel.services.cities import lookup_city, parse_city_state


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Austin, TX", ("Austin", "TX")),
        ("austin, tx", ("Austin".lower(), "TX")),
        ("Austin, Texas", ("Austin", "TX")),
        ("Austin, TX, USA", ("Austin", "TX")),
        ("Washington, District of Columbia", ("Washington", "DC")),
    ],
)
def test_parse_city_state(text, expected):
    got = parse_city_state(text)
    assert got is not None and got[0].lower() == expected[0].lower() and got[1] == expected[1]


@pytest.mark.parametrize("text", ["Austin", "1600 Pennsylvania Ave, Washington, DC", "Paris, France", ""])
def test_parse_rejects_non_city_state(text):
    assert parse_city_state(text) is None


def test_lookup_known_cities():
    place, label = lookup_city("Los Angeles, CA")
    assert label == "Los Angeles, CA" and 33.8 < place.lat < 34.3 and -118.6 < place.lng < -118.0
    place, _ = lookup_city("New York, NY")
    assert 40.5 < place.lat < 41.0
    assert lookup_city("Nowhereville, TX") is None

"""Readable, unique page names for the station pages (/station/<slug>/)."""

from stepfree.build import slugify, unique_slugs


def test_page_names_are_readable():
    assert slugify("Houten Castellum") == "houten-castellum"
    assert slugify("'s-Hertogenbosch Oost") == "s-hertogenbosch-oost"
    assert slugify("Amsterdam Bijlmer ArenA") == "amsterdam-bijlmer-arena"
    assert slugify("Liège-Guillemins") == "liege-guillemins"
    assert slugify("Den Haag HS") == "den-haag-hs"


def test_page_names_never_collide():
    assert unique_slugs({"HGL": "Hengelo", "XHG": "Hengelo", "UT": "Utrecht Centraal"}) == {
        "HGL": "hengelo-hgl",
        "XHG": "hengelo-xhg",
        "UT": "utrecht-centraal",
    }

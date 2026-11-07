import pytest
import requests
import responses

from app.rickandmorty import (
    Character,
    UpstreamError,
    build_session,
    find_characters,
    matches,
    to_csv,
)
from tests.conftest import API, character


def page(results, next_url=None):
    return {"info": {"count": len(results), "pages": 2, "next": next_url, "prev": None}, "results": results}


def test_matches_all_three_conditions():
    assert matches(character(1, "Rick Sanchez"))
    assert not matches(character(2, "Alien", species="Alien"))
    assert not matches(character(3, "Dead guy", status="Dead"))
    assert not matches(character(4, "Unknown status", status="unknown"))
    assert not matches(character(5, "Citadel resident", origin="Citadel of Ricks"))


def test_humanoid_is_not_human():
    # the API filters species by substring, so Humanoid can come back for species=Human
    assert not matches(character(6, "Humanoid", species="Humanoid"))


@pytest.mark.parametrize(
    "origin, prefix, exact",
    [
        ("Earth", True, True),
        ("Earth (C-137)", True, False),
        ("Earth (Replacement Dimension)", True, False),
        ("Earthlings", False, False),
        ("unknown", False, False),
        ("Nuptia 4", False, False),
    ],
)
def test_origin_modes(origin, prefix, exact):
    raw = character(7, "X", origin=origin)
    assert matches(raw, "prefix") is prefix
    assert matches(raw, "exact") is exact


@responses.activate
def test_find_characters_follows_pagination_and_filters():
    page2 = f"{API}/character?page=2&species=Human&status=Alive"
    responses.get(
        f"{API}/character",
        json=page([character(1, "Rick Sanchez"), character(2, "Alien Rick", species="Alien")], page2),
        match=[responses.matchers.query_param_matcher({"species": "Human", "status": "Alive"})],
    )
    responses.get(
        page2,
        json=page([character(3, "Morty Smith", origin="Earth (Replacement Dimension)", location="Earth")]),
    )
    found = find_characters(build_session())
    assert [c.name for c in found] == ["Rick Sanchez", "Morty Smith"]
    assert found[0].location == "Citadel of Ricks"
    assert found[1].image.endswith("/3.jpeg")


@responses.activate
def test_no_results_is_an_empty_list():
    responses.get(f"{API}/character", status=404, json={"error": "There is nothing here"})
    assert find_characters(build_session()) == []


@responses.activate
def test_upstream_http_error():
    responses.get(f"{API}/character", status=500)
    with pytest.raises(UpstreamError):
        find_characters(build_session())


@responses.activate
def test_upstream_unreachable():
    responses.get(f"{API}/character", body=requests.ConnectionError("boom"))
    with pytest.raises(UpstreamError):
        find_characters(build_session())


@responses.activate
def test_unexpected_payload():
    responses.get(f"{API}/character", json={"nope": True})
    with pytest.raises(UpstreamError):
        find_characters(build_session())


def test_csv_has_header_and_quotes_commas():
    text = to_csv(
        [
            Character("Rick Sanchez", "Earth", "https://x/1.jpeg"),
            Character("Smith, Jerry", "Earth, Prime", "https://x/2.jpeg"),
        ]
    )
    lines = text.splitlines()
    assert lines[0] == "Name,Location,Image"
    assert lines[1] == "Rick Sanchez,Earth,https://x/1.jpeg"
    assert lines[2] == '"Smith, Jerry","Earth, Prime",https://x/2.jpeg'

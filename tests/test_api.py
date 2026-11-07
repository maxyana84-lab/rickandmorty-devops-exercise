import pytest

from app.api import create_app
from app.rickandmorty import Character, UpstreamError

CHARS = [
    Character("Rick Sanchez", "Citadel of Ricks", "https://rickandmortyapi.com/api/character/avatar/1.jpeg"),
    Character("Morty Smith", "Earth", "https://rickandmortyapi.com/api/character/avatar/2.jpeg"),
]


@pytest.fixture
def client():
    return create_app(loader=lambda: CHARS, cache_ttl=60).test_client()


def test_healthcheck(client):
    response = client.get("/healthcheck")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_characters_json(client):
    response = client.get("/characters")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 2
    assert body["characters"][0] == {
        "name": "Rick Sanchez",
        "location": "Citadel of Ricks",
        "image": "https://rickandmortyapi.com/api/character/avatar/1.jpeg",
    }


def test_characters_csv(client):
    response = client.get("/characters.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.get_data(as_text=True).splitlines()[0] == "Name,Location,Image"


def test_upstream_failure_is_a_502_and_healthcheck_still_works():
    def broken():
        raise UpstreamError("down")

    client = create_app(loader=broken, cache_ttl=60).test_client()
    response = client.get("/characters")
    assert response.status_code == 502
    assert response.get_json() == {"error": "down"}
    assert client.get("/healthcheck").status_code == 200


def test_result_is_cached():
    calls = []

    def loader():
        calls.append(1)
        return CHARS

    client = create_app(loader=loader, cache_ttl=60).test_client()
    client.get("/characters")
    client.get("/characters.csv")
    assert len(calls) == 1


def test_cache_expires():
    calls = []

    def loader():
        calls.append(1)
        return CHARS

    client = create_app(loader=loader, cache_ttl=0).test_client()
    client.get("/characters")
    client.get("/characters")
    assert len(calls) == 2

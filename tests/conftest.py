import pytest

API = "https://rickandmortyapi.com/api"


def character(cid, name, species="Human", status="Alive", origin="Earth (C-137)", location="Citadel of Ricks"):
    return {
        "id": cid,
        "name": name,
        "species": species,
        "status": status,
        "origin": {"name": origin, "url": ""},
        "location": {"name": location, "url": ""},
        "image": f"https://rickandmortyapi.com/api/character/avatar/{cid}.jpeg",
    }


@pytest.fixture
def api_url():
    return API


@pytest.fixture(autouse=True)
def default_api_url(monkeypatch):
    """Tests must not depend on RICKANDMORTY_API_URL being set in the environment."""
    monkeypatch.setattr("app.rickandmorty.API_URL", API)

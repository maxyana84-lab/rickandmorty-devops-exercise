"""Client and filtering logic for the Rick and Morty API (https://rickandmortyapi.com)."""
from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = os.environ.get("RICKANDMORTY_API_URL", "https://rickandmortyapi.com/api")
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10"))

CSV_HEADER = ("Name", "Location", "Image")

# The API has several Earths: "Earth (C-137)", "Earth (Replacement Dimension)", ...
EARTH_PREFIX = re.compile(r"^Earth(?: \(.*\))?$")
EARTH_EXACT = re.compile(r"^Earth$")


class UpstreamError(RuntimeError):
    """The Rick and Morty API could not be reached or answered with an error."""


@dataclass(frozen=True)
class Character:
    name: str
    location: str
    image: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "location": self.location, "image": self.image}


def build_session() -> requests.Session:
    """HTTP session that retries transient failures (429 and 5xx) with a back-off."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "rickandmorty-devops-exercise/1.0"
    return session


def iter_raw_characters(
    session: requests.Session, species: str, status: str, api_url: str | None = None
) -> Iterator[dict]:
    """Yield every character the API returns for the filters, following the pagination.

    The API paginates (20 per page) and puts the link to the next page in info["next"].
    """
    url: str | None = f"{(api_url or API_URL).rstrip('/')}/character"
    params: dict[str, str] | None = {"species": species, "status": status}
    while url:
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise UpstreamError(f"cannot reach the Rick and Morty API: {exc}") from exc
        if response.status_code == 404:  # the API answers 404 when nothing matches
            return
        if not response.ok:
            raise UpstreamError(f"Rick and Morty API answered HTTP {response.status_code}")
        try:
            payload = response.json()
            results = payload["results"]
            url = payload["info"]["next"]
        except (ValueError, KeyError, TypeError) as exc:
            raise UpstreamError("unexpected response from the Rick and Morty API") from exc
        params = None  # the "next" URL already carries the whole query string
        yield from results


def matches(raw: dict, origin_mode: str = "prefix") -> bool:
    """Species is Human, status is Alive and origin is Earth.

    The API filters `species` and `status` by substring (for example "Human" also matches
    "Humanoid") and has no origin filter at all, so every condition is checked here again.
    origin_mode "prefix" accepts "Earth" and "Earth (...)", "exact" accepts only "Earth".
    """
    origin_pattern = EARTH_EXACT if origin_mode == "exact" else EARTH_PREFIX
    return (
        str(raw.get("species", "")).lower() == "human"
        and str(raw.get("status", "")).lower() == "alive"
        and bool(origin_pattern.match(str((raw.get("origin") or {}).get("name", ""))))
    )


def find_characters(
    session: requests.Session | None = None,
    origin_mode: str = "prefix",
    api_url: str | None = None,
) -> list[Character]:
    """Alive humans from Earth as a list of (name, location, image)."""
    session = session or build_session()
    return [
        Character(
            name=raw["name"],
            location=(raw.get("location") or {}).get("name", ""),
            image=raw.get("image", ""),
        )
        for raw in iter_raw_characters(session, "human", "alive", api_url)
        if matches(raw, origin_mode)
    ]


def to_csv(characters: list[Character]) -> str:
    """Name,Location,Image rows; the csv module quotes names or places that contain commas."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for character in characters:
        writer.writerow((character.name, character.location, character.image))
    return buffer.getvalue()

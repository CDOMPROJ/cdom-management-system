import pytest
from httpx import AsyncClient

# Tells pytest to run these asynchronously
pytestmark = pytest.mark.asyncio


async def test_register_and_search_baptism(async_client: AsyncClient):
    # ==========================================
    # 1. TEST THE REGISTRATION (POST)
    # ==========================================
    new_baptism_data = {
        "first_name": "TestBaby",
        "last_name": "Testing",
        "dob": "2026-01-01",
        "date_of_baptism": "2026-02-01",
        "place_of_birth": "Test Hospital",
        "father_first_name": "John",
        "father_last_name": "Testing",
        "mother_first_name": "Mary",
        "mother_last_name": "Testing",
        "godparents": "Godfather Bob",
        "minister_of_baptism": "Fr. Test",
        "village": "Test Village",
        "center": "Test Center"
    }

    # Fire the request!
    post_response = await async_client.post("/api/v1/baptisms/", json=new_baptism_data)

    # Prove it succeeded
    assert post_response.status_code == 201
    data = post_response.json()
    assert "canonical_reference" in data
    assert data["message"] == "Baptism registered successfully."

    # ==========================================
    # 2. TEST THE RAPIDFUZZ SEARCH (GET)
    # ==========================================
    # We will search for a slight typo: "TestBby" instead of "TestBaby"
    search_response = await async_client.get("/api/v1/baptisms/search?q=TestBby")

    # Prove the search endpoint is online
    assert search_response.status_code == 200
    search_data = search_response.json()

    # Prove RapidFuzz successfully caught the typo and returned our baby
    assert search_data["scope"] == "LOCAL"
    assert len(search_data["results"]) > 0
    assert search_data["results"][0]["first_name"] == "TestBaby"

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.live_model
def test_live_api_health_and_allowed_recommendation_smoke():
    from weilv.api.app import app

    payload = {
        "user_id": "poc-stage5-api-001",
        "query": "我写作业快一个小时了，现在有10分钟休息。",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 10,
        "vision_abnormal": False,
        "physical_discomfort": False,
        "medical_request": False,
        "cannot_move": False,
        "unstable_environment": False,
        "sleep_being_crowded": False,
    }

    with TestClient(app) as client:
        health = client.get("/health")
        recommendation = client.post("/api/v1/recommendations", json=payload)

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert recommendation.status_code == 200
    body = recommendation.json()
    assert body["status"] == "allowed"
    assert body["selected_task"] is not None
    assert body["sources"]

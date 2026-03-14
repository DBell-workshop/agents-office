from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_training_flow_smoke() -> None:
    course_resp = client.post(
        "/api/v1/training/courses",
        json={
            "product_id": "prod-001",
            "product_name": "Phone X",
            "objective": "training",
            "required_points": ["battery", "camera"],
            "product_facts": {"installments": "12 installments"},
        },
    )
    assert course_resp.status_code == 200
    course_id = course_resp.json()["data"]["course_id"]

    gen_resp = client.post(
        f"/api/v1/training/courses/{course_id}:generate-content",
        json={"scene": "in_store", "script_style": "natural", "language": "zh-CN"},
    )
    assert gen_resp.status_code == 200
    gen_task_id = gen_resp.json()["data"]["task_id"]

    task_resp = client.get(f"/api/v1/tasks/{gen_task_id}")
    assert task_resp.status_code == 200
    assert task_resp.json()["data"]["status"] == "succeeded"

    attempt_resp = client.post(
        "/api/v1/training/attempts",
        json={
            "course_id": course_id,
            "user_id": "guide-001",
            "mock_transcript": "This has battery and camera. We support 24 installments ...",
        },
    )
    assert attempt_resp.status_code == 200
    attempt_id = attempt_resp.json()["data"]["attempt_id"]

    eval_resp = client.post(f"/api/v1/training/attempts/{attempt_id}:evaluate", json={"rubric_version": "v1"})
    assert eval_resp.status_code == 200
    eval_task_id = eval_resp.json()["data"]["task_id"]

    report_resp = client.get(f"/api/v1/tasks/{eval_task_id}")
    assert report_resp.status_code == 200
    report_payload = report_resp.json()["data"]
    assert report_payload["status"] == "succeeded"
    assert "scores" in report_payload["output"]


def test_comparison_flow_smoke() -> None:
    create_resp = client.post(
        "/api/v1/comparison/tasks",
        json={
            "source_product_id": "prod-001",
            "source_product_name": "Phone X",
            "targets": [
                {"platform": "jd", "url": "https://item.jd.com/mock"},
                {"platform": "taobao", "url": "https://detail.tmall.com/mock"},
            ],
        },
    )
    assert create_resp.status_code == 200
    comparison_task_id = create_resp.json()["data"]["comparison_task_id"]

    run_resp = client.post(f"/api/v1/comparison/tasks/{comparison_task_id}:run", json={"template_version": "v1"})
    assert run_resp.status_code == 200
    run_task_id = run_resp.json()["data"]["task_id"]

    task_resp = client.get(f"/api/v1/tasks/{run_task_id}")
    assert task_resp.status_code == 200
    payload = task_resp.json()["data"]
    assert payload["status"] == "succeeded"
    assert len(payload["output"]["offers"]) == 2

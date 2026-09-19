import json

import httpx2
from tonedown.backends.jev import JevBackend, build_request
from tonedown.schema import Category


def _handler(request: httpx2.Request) -> httpx2.Response:
    body = json.loads(request.content)
    assert request.url.path == "/v1/systemone"
    answers = {}
    for name, q in body["questions"].items():
        if q["type"] == "score":
            answers[name] = {
                "type": "score",
                "score": 2.0,
                "confidence": 0.9,
                "legend": {str(i): c for i, c in enumerate(q["criteria"])},
                "probabilities": {"0": 0.0, "1": 0.05, "2": 0.9, "3": 0.05, "4": 0.0},
            }
        else:
            hot = name.endswith("_cat_harassment") or name.endswith("_targeted")
            answers[name] = {"type": "noul", "noul": 0.9 if hot else 0.05}
    return httpx2.Response(
        200, json={"model": "jev-test", "answers": answers, "usage": {"input_tokens": 300, "output_tokens": 30}}
    )


def test_build_request_names_questions_per_item():
    state, qs = build_request(["a", "b"])
    assert list(state) == ["c0", "c1"]
    assert "c1_risk" in qs and "c0_cat_hate" in qs and "c1_targeted" in qs
    assert len(qs) == 2 * (2 + len(Category))


def test_parse_batch_through_mock_transport():
    backend = JevBackend(api_key="test", batch_size=2, transport=httpx2.MockTransport(_handler))
    raws = backend.grade(["x", "y", "z"])  # two calls: [x, y] and [z]
    assert len(raws) == 3
    assert raws[0].level_argmax == 2 and abs(raws[0].level - 2.0) < 1e-6
    assert raws[0].categories[Category.HARASSMENT] == 0.9 and raws[0].categories[Category.HATE] == 0.05
    assert raws[0].targeted == 0.9 and raws[0].confidence == 0.9
    assert raws[0].input_tokens == 150.0 and raws[2].input_tokens == 300.0
    assert raws[0].backend == "jev:jev-latest"

"""Domain detection must recognise modern product/tech requests as software.

Regression for the classification gap: product-phrased technical requests like
"Build me a dashboard that shows my Stripe revenue" or "My React app re-renders"
fell through to the "general" domain, so no developer persona/role was applied.
The keyword set was missing modern frameworks/products, and substring matching
mislabelled words like "rapid" (contains "api") as software.
"""

from app.heuristics import detect_domain


def test_dashboard_stripe_request_is_software():
    domain, _ = detect_domain("Build me a dashboard that shows my Stripe revenue")
    assert domain == "software"


def test_react_app_request_is_software():
    domain, _ = detect_domain("My React app re-renders too much, help me fix the performance")
    assert domain == "software"


def test_nextjs_typescript_request_is_software():
    domain, _ = detect_domain("Create a Next.js frontend with TypeScript and Tailwind")
    assert domain == "software"


def test_existing_python_request_still_software():
    domain, _ = detect_domain("Write a Python function to parse nginx logs")
    assert domain == "software"


def test_word_boundary_avoids_rapid_api_false_positive():
    # "rapid" contains "api" but is not a software request
    domain, _ = detect_domain("We need rapid iteration on our marketing copy")
    assert domain != "software"

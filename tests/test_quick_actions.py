# ruff: noqa: E402
import sys
from unittest.mock import MagicMock, patch

# Mock the missing modules in sys.modules before importing app.quick_actions
mock_search_history = MagicMock()
mock_search_history.get_search_history_manager = MagicMock()

mock_snippets = MagicMock()
mock_snippets.get_snippets_manager = MagicMock()

sys.modules["app.search_history"] = mock_search_history
sys.modules["app.snippets"] = mock_snippets

# Now we can safely import app.quick_actions
import pytest
from app.quick_actions import QuickActions, get_quick_actions


def test_get_quick_actions_singleton():
    with patch("app.quick_actions.get_search_history_manager"), patch(
        "app.quick_actions.get_favorites_manager"
    ), patch("app.quick_actions.get_templates_manager"), patch(
        "app.quick_actions.get_snippets_manager"
    ):
        inst1 = get_quick_actions()
        inst2 = get_quick_actions()
        assert inst1 is inst2


@pytest.fixture
def mock_managers():
    with patch("app.quick_actions.get_search_history_manager") as m_hist, patch(
        "app.quick_actions.get_favorites_manager"
    ) as m_fav, patch("app.quick_actions.get_templates_manager") as m_temp, patch(
        "app.quick_actions.get_snippets_manager"
    ) as m_snip:
        hist_mgr = MagicMock()
        fav_mgr = MagicMock()
        temp_mgr = MagicMock()
        snip_mgr = MagicMock()

        m_hist.return_value = hist_mgr
        m_fav.return_value = fav_mgr
        m_temp.return_value = temp_mgr
        m_snip.return_value = snip_mgr

        yield hist_mgr, fav_mgr, temp_mgr, snip_mgr


def test_get_last_search(mock_managers):
    hist_mgr, _, _, _ = mock_managers

    # 1. Test empty search history
    hist_mgr.get_recent.return_value = []
    actions = QuickActions()
    assert actions.get_last_search() is None

    # 2. Test search history present
    mock_entry = MagicMock()
    mock_entry.query = "summarize PDF"
    mock_entry.result_count = 5
    mock_entry.timestamp = "2026-06-26"
    mock_entry.types_filter = None
    mock_entry.min_score = 0.8
    hist_mgr.get_recent.return_value = [mock_entry]

    res = actions.get_last_search()
    assert res is not None
    assert res["query"] == "summarize PDF"
    assert res["result_count"] == 5
    assert res["min_score"] == 0.8


def test_get_top_favorites(mock_managers):
    _, fav_mgr, _, _ = mock_managers

    # 1. Test empty favorites
    fav_mgr.get_all.return_value = []
    actions = QuickActions()
    assert actions.get_top_favorites() == []

    # 2. Test sorting favorites by score
    fav1 = MagicMock()
    fav1.id = "f1"
    fav1.prompt_text = "prompt 1"
    fav1.score = 0.5
    fav1.domain = "dev"
    fav1.tags = ["tag1"]
    fav1.notes = "note1"
    fav1.use_count = 1
    fav1.timestamp = "time1"

    fav2 = MagicMock()
    fav2.id = "f2"
    fav2.prompt_text = "prompt 2"
    fav2.score = 0.9

    fav_mgr.get_all.return_value = [fav1, fav2]

    res = actions.get_top_favorites(limit=1)
    assert len(res) == 1
    assert res[0]["id"] == "f2"  # Higher score first
    assert res[0]["score"] == 0.9


def test_get_random_template(mock_managers):
    _, _, temp_mgr, _ = mock_managers

    # 1. Empty templates
    temp_mgr.list_templates.return_value = []
    actions = QuickActions()
    assert actions.get_random_template() is None

    # 2. Template present
    tpl = MagicMock()
    tpl.name = "template 1"
    tpl.description = "desc 1"
    tpl.template_text = "text 1"
    tpl.category = "general"
    tpl.tags = []
    tpl.variables = []

    temp_mgr.list_templates.return_value = [tpl]
    res = actions.get_random_template()
    assert res is not None
    assert res["name"] == "template 1"


def test_get_random_snippet(mock_managers):
    _, _, _, snip_mgr = mock_managers

    # 1. Empty snippets
    snip_mgr.get_all.return_value = []
    actions = QuickActions()
    assert actions.get_random_snippet() is None

    # 2. Snippet present
    snip = MagicMock()
    snip.title = "snip 1"
    snip.content = "content 1"
    snip.category = "code"
    snip.description = "desc 1"
    snip.tags = []
    snip.use_count = 5

    snip_mgr.get_all.return_value = [snip]
    res = actions.get_random_snippet()
    assert res is not None
    assert res["title"] == "snip 1"


def test_get_random_item(mock_managers):
    _, _, temp_mgr, snip_mgr = mock_managers
    actions = QuickActions()

    # Mock template and snippet
    tpl = MagicMock(name="tpl")
    tpl.name = "template 1"
    tpl.variables = []
    temp_mgr.list_templates.return_value = [tpl]

    snip = MagicMock(name="snip")
    snip.title = "snip 1"
    snip_mgr.get_all.return_value = [snip]

    # Test specific item_type 'template'
    res = actions.get_random_item(item_type="template")
    assert res["type"] == "template"
    assert res["data"]["name"] == "template 1"

    # Test specific item_type 'snippet'
    res = actions.get_random_item(item_type="snippet")
    assert res["type"] == "snippet"
    assert res["data"]["title"] == "snip 1"

    # Test random selection (none requested)
    res_rand = actions.get_random_item()
    assert res_rand["type"] in ["template", "snippet"]

    # Test empty database fallback
    temp_mgr.list_templates.return_value = []
    snip_mgr.get_all.return_value = []
    assert actions.get_random_item() is None

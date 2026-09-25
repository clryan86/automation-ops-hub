import pytest

from app.config import Settings
from app.services.actions import ActionError, execute_action, get_path, render_template, safe_calculate

SETTINGS = Settings(database_url="sqlite:///:memory:", scheduler_enabled=False)


def test_nested_get_and_template_render():
    context = {"lead": {"name": "Chris", "score": 88}}
    assert get_path(context, "lead.name") == "Chris"
    assert render_template("{{lead.name}} scored {{lead.score}}", context) == "Chris scored 88"


def test_safe_calculate_uses_only_numeric_expression():
    assert safe_calculate("quantity * price + fee", {"quantity": 3, "price": 20, "fee": 5}) == 65
    with pytest.raises(ActionError):
        safe_calculate("__import__('os').system('echo nope')", {})


def test_execute_actions_build_context():
    context = {"lead": {"name": "Ava", "email": "ava@example.com"}}
    execute_action("regex_extract", {"source": "lead.email", "pattern": "@(.+)$", "group": 1, "path": "domain"}, context, SETTINGS)
    execute_action("template", {"path": "message", "template": "Hello {{lead.name}} at {{domain}}"}, context, SETTINGS)
    assert context["domain"] == "example.com"
    assert context["message"] == "Hello Ava at example.com"

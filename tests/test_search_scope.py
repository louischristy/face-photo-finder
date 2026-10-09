import pytest

from app.search_scope import build_search_scope


def test_empty_selection_means_all_project_sources():
    scope = build_search_scope(10, [])
    assert scope.project_id == 10
    assert scope.all_sources is True


def test_selected_sources_are_deduplicated():
    scope = build_search_scope(10, [1, 2, 2, 3])
    assert scope.source_ids == (1, 2, 3)
    assert scope.all_sources is False


def test_sources_must_belong_to_selected_project():
    scope = build_search_scope(10, [1, 7])
    with pytest.raises(ValueError):
        scope.validate_for_project({1, 2, 3})

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchScope:
    """Project-bound source selection used by face search and result downloads."""

    project_id: int
    source_ids: tuple[int, ...] = ()

    @property
    def all_sources(self) -> bool:
        return not self.source_ids

    def validate_for_project(self, project_source_ids: set[int]) -> None:
        invalid = set(self.source_ids) - project_source_ids
        if invalid:
            raise ValueError("Search scope contains sources outside the selected project")


def build_search_scope(project_id: int, selected_source_ids: list[int] | None) -> SearchScope:
    unique = tuple(dict.fromkeys(selected_source_ids or []))
    return SearchScope(project_id=project_id, source_ids=unique)

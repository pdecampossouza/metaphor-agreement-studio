from metaphor_agreement_studio.ui.navigation import Route, route_requires_validated_dataset


def test_analysis_and_publication_routes_are_locked_until_validation() -> None:
    assert route_requires_validated_dataset(Route.AGREEMENT) is True
    assert route_requires_validated_dataset(Route.DISAGREEMENT_REVIEW) is True
    assert route_requires_validated_dataset(Route.STATISTICS) is True
    assert route_requires_validated_dataset(Route.FIGURES) is True
    assert route_requires_validated_dataset(Route.REPORTING) is True
    assert route_requires_validated_dataset(Route.DATA_VALIDATION) is False
    assert route_requires_validated_dataset(Route.ANNOTATIONS) is False
    assert route_requires_validated_dataset(Route.PROJECT) is False

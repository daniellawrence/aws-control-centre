import pytest

from app import validate_tags


@pytest.mark.parametrize(
    'user_tags,machine_tags,allowed', [
        ({'CostCenter': 'CC01'}, {'CostCenter': 'CC01'}, True),
        ({'CostCenter': 'CC02'}, {'CostCenter': 'CC01'}, False),
        ({'CostCenter': 'CC01'}, {'CostCenter': 'CC02'}, False),
        ({'CostCenter': ['CC02', 'CC01']}, {'CostCenter': 'CC01'}, True),
        ({'CostCenter': ['CC02', '!CC01']}, {'CostCenter': 'CC01'}, False),
        # Simple '!' will force the match to fail
        ({'Environment': 'Dev'}, {'Environment': 'Dev'}, True),
        ({'Environment': '!Dev'}, {'Environment': 'Dev'}, False),
        #
        ({'Environment': 'Dev', 'CostCentre': 'CC01'},
         {'Environment': 'Dev', 'CostCentre': 'CC01'}, True),
        # User can have many things to match agianst
        ({'Environment': 'Dev', 'CostCentre': ['CC01', 'CC02']},
         {'Environment': 'Dev', 'CostCentre': 'CC01'}, True),
        # A single match is not good enough
        ({'Environment': 'Dev', 'CostCentre': ['CC01', 'CC02']},
         {'Environment': 'Prod', 'CostCentre': 'CC01'}, False),
        # If user has tags, then te machine must match
        ({'Environment': 'Dev', 'CostCentre': ['CC01', 'CC02']},
         {'CostCentre': 'CC01'}, False),
    ]
)
def test_allowed_by_tags(user_tags, machine_tags, allowed):
    results = validate_tags(user_tags, machine_tags)
    assert results == allowed


if __name__ == '__main__':
    test_allowed_by_tags()

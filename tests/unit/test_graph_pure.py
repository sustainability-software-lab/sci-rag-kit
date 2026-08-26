from pathlib import Path

from sci_rag.domain import load_domain
from sci_rag.graph import detect_communities, parse_extraction

DOMAIN = load_domain(Path(__file__).parents[2] / "domain")


def test_parse_extraction_keeps_valid_and_canonicalizes_types() -> None:
    payload = {
        "entities": [
            {
                "name": "rice straw",
                "type": "feedstock",
                "description": "a residue",
                "passages": [1],
            },
            {"name": "Colusa County", "type": "REGION", "passages": [2]},
        ],
        "relationships": [
            {
                "source": "rice straw",
                "target": "Colusa County",
                "type": "located_in",
                "evidence": "grown in Colusa",
                "passage": 1,
            }
        ],
    }
    entities, relationships = parse_extraction(payload, DOMAIN, batch_size=2)
    assert [e.entity_type for e in entities] == ["Feedstock", "Region"]
    assert relationships[0].relation_type == "LOCATED_IN"


def test_parse_extraction_drops_garbage_instead_of_guessing() -> None:
    payload = {
        "entities": [
            {"name": "rice straw", "type": "Feedstock"},
            {"name": "", "type": "Feedstock"},
            {"name": "mystery", "type": "NotARealType"},
            {"name": "RICE STRAW", "type": "Feedstock"},  # duplicate, case-insensitive
        ],
        "relationships": [
            {"source": "rice straw", "target": "mystery", "type": "PRODUCES"},  # dangling target
            {"source": "rice straw", "target": "rice straw", "type": "PRODUCES"},  # self edge
            {"source": "rice straw", "target": "rice straw2", "type": "NOT_A_REL"},
        ],
    }
    entities, relationships = parse_extraction(payload, DOMAIN, batch_size=1)
    assert [e.name for e in entities] == ["rice straw"]
    assert relationships == []


def test_parse_extraction_rejects_non_dict_payload() -> None:
    assert parse_extraction("not json-shaped", DOMAIN, batch_size=1) == ([], [])
    assert parse_extraction(["list"], DOMAIN, batch_size=1) == ([], [])


def test_detect_communities_separates_two_cliques() -> None:
    nodes = ["a1", "a2", "a3", "b1", "b2", "b3"]
    edges = [
        ("a1", "a2"),
        ("a2", "a3"),
        ("a1", "a3"),
        ("b1", "b2"),
        ("b2", "b3"),
        ("b1", "b3"),
    ]
    groups = detect_communities(nodes, edges)
    member_sets = sorted(tuple(members) for members in groups.values())
    assert member_sets == [("a1", "a2", "a3"), ("b1", "b2", "b3")]


def test_detect_communities_is_deterministic() -> None:
    nodes = [f"n{i}" for i in range(12)]
    edges = [(f"n{i}", f"n{(i + 1) % 6}") for i in range(6)] + [
        (f"n{6 + i}", f"n{6 + (i + 1) % 6}") for i in range(6)
    ]
    first = detect_communities(nodes, edges)
    second = detect_communities(nodes, edges)
    assert first == second


def test_detect_communities_handles_isolated_nodes_and_empty() -> None:
    assert detect_communities([], []) == {}
    groups = detect_communities(["solo"], [])
    assert groups == {"solo": ["solo"]}

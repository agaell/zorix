from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from zorix_resource_graph import ResourceRelation


class ResourceRelationTest(unittest.TestCase):
    def test_creates_relation(self) -> None:
        relation = ResourceRelation(
            source_id="service:api",
            target_id="database:main",
            type="depends_on",
            metadata={"reason": "runtime"},
        )

        self.assertEqual(relation.source_id, "service:api")
        self.assertEqual(relation.target_id, "database:main")
        self.assertEqual(relation.type, "depends_on")
        self.assertEqual(relation.metadata, {"reason": "runtime"})

    def test_relation_is_frozen(self) -> None:
        relation = ResourceRelation("a", "b", "depends_on")

        with self.assertRaises(FrozenInstanceError):
            relation.source_id = "other"

    def test_relation_uses_slots(self) -> None:
        relation = ResourceRelation("a", "b", "depends_on")

        self.assertFalse(hasattr(relation, "__dict__"))

    def test_required_strings_are_stripped(self) -> None:
        relation = ResourceRelation(" source ", " target ", " depends_on ")

        self.assertEqual(relation.source_id, "source")
        self.assertEqual(relation.target_id, "target")
        self.assertEqual(relation.type, "depends_on")

    def test_empty_source_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ResourceRelation(" ", "target", "depends_on")

    def test_empty_target_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ResourceRelation("source", "", "depends_on")

    def test_empty_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ResourceRelation("source", "target", "\t")

    def test_non_string_required_values_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ResourceRelation(1, "target", "depends_on")

        with self.assertRaises(TypeError):
            ResourceRelation("source", object(), "depends_on")

        with self.assertRaises(TypeError):
            ResourceRelation("source", "target", None)

    def test_metadata_is_copied(self) -> None:
        metadata = {"reason": "runtime"}
        relation = ResourceRelation("source", "target", "depends_on", metadata)

        metadata["reason"] = "changed"

        self.assertEqual(relation.metadata, {"reason": "runtime"})

    def test_metadata_is_readable(self) -> None:
        relation = ResourceRelation("source", "target", "depends_on", {"reason": "runtime"})

        self.assertEqual(relation.metadata["reason"], "runtime")

    def test_metadata_cannot_be_modified_from_relation(self) -> None:
        relation = ResourceRelation("source", "target", "depends_on", {"reason": "runtime"})

        with self.assertRaises(TypeError):
            relation.metadata["reason"] = "changed"

    def test_non_string_metadata_key_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ResourceRelation("source", "target", "depends_on", {1: "value"})

    def test_non_string_metadata_value_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ResourceRelation("source", "target", "depends_on", {"key": 1})

    def test_identity_contains_source_type_target(self) -> None:
        relation = ResourceRelation("source", "target", "depends_on")

        self.assertEqual(relation.identity, ("source", "depends_on", "target"))

    def test_metadata_is_not_part_of_identity(self) -> None:
        first = ResourceRelation("source", "target", "depends_on", {"a": "1"})
        second = ResourceRelation("source", "target", "depends_on", {"a": "2"})

        self.assertEqual(first.identity, second.identity)

    def test_relations_with_same_identity_and_different_metadata_are_equal(self) -> None:
        first = ResourceRelation("source", "target", "depends_on", {"a": "1"})
        second = ResourceRelation("source", "target", "depends_on", {"a": "2"})

        self.assertEqual(first, second)

    def test_relation_hash_uses_identity_not_metadata(self) -> None:
        first = ResourceRelation("source", "target", "depends_on", {"a": "1"})
        second = ResourceRelation("source", "target", "depends_on", {"a": "2"})

        self.assertEqual(hash(first), hash(second))
        self.assertEqual({first, second}, {first})

    def test_self_relation_is_allowed(self) -> None:
        relation = ResourceRelation("resource-a", "resource-a", "references")

        self.assertEqual(relation.identity, ("resource-a", "references", "resource-a"))

    def test_metadata_order_is_preserved(self) -> None:
        relation = ResourceRelation(
            "source",
            "target",
            "depends_on",
            {"first": "1", "second": "2"},
        )

        self.assertEqual(list(relation.metadata.items()), [("first", "1"), ("second", "2")])


if __name__ == "__main__":
    unittest.main()

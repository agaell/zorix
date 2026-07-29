from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from zorix_core_model import Resource
from zorix_resource_graph import ResourceGraphBuilder, ResourceRelation
from zorix_topology_engine import (
    TopologyProviderError,
    TopologyResult,
    TopologyStatus,
)


class TopologyModelsTest(unittest.TestCase):
    def test_status_contains_success(self) -> None:
        self.assertIsInstance(TopologyStatus.SUCCESS, TopologyStatus)

    def test_status_contains_partial(self) -> None:
        self.assertIsInstance(TopologyStatus.PARTIAL, TopologyStatus)

    def test_status_contains_failed(self) -> None:
        self.assertIsInstance(TopologyStatus.FAILED, TopologyStatus)

    def test_provider_error_is_frozen(self) -> None:
        error = TopologyProviderError("example.Provider", "RuntimeError", "failed")

        with self.assertRaises(FrozenInstanceError):
            error.message = "changed"

    def test_creates_provider_error(self) -> None:
        error = TopologyProviderError("example.Provider", "RuntimeError", "failed")

        self.assertEqual(error.provider, "example.Provider")
        self.assertEqual(error.error_type, "RuntimeError")
        self.assertEqual(error.message, "failed")

    def test_success_result_without_providers(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph(),
            errors=(),
            provider_count=0,
            successful_provider_count=0,
        )

        self.assertIs(result.status, TopologyStatus.SUCCESS)

    def test_success_result_with_successful_provider(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph(),
            errors=(),
            provider_count=1,
            successful_provider_count=1,
        )

        self.assertEqual(result.failed_provider_count, 0)

    def test_partial_result_with_successful_and_failed_providers(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.PARTIAL,
            graph=_graph(),
            errors=(TopologyProviderError("example.Provider", "RuntimeError", "failed"),),
            provider_count=2,
            successful_provider_count=1,
        )

        self.assertIs(result.status, TopologyStatus.PARTIAL)

    def test_failed_result_when_all_providers_failed(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.FAILED,
            graph=_graph(),
            errors=(TopologyProviderError("example.Provider", "RuntimeError", "failed"),),
            provider_count=1,
            successful_provider_count=0,
        )

        self.assertIs(result.status, TopologyStatus.FAILED)

    def test_failed_provider_count(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.PARTIAL,
            graph=_graph(),
            errors=(TopologyProviderError("example.Provider", "RuntimeError", "failed"),),
            provider_count=3,
            successful_provider_count=2,
        )

        self.assertEqual(result.failed_provider_count, 1)

    def test_relation_count(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph(ResourceRelation("service:api", "database:main", "depends_on")),
            errors=(),
            provider_count=1,
            successful_provider_count=1,
        )

        self.assertEqual(result.relation_count, 1)

    def test_errors_must_be_tuple(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=[],
                provider_count=0,
                successful_provider_count=0,
            )

    def test_negative_provider_count_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=(),
                provider_count=-1,
                successful_provider_count=0,
            )

    def test_negative_successful_provider_count_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=(),
                provider_count=1,
                successful_provider_count=-1,
            )

    def test_successful_provider_count_cannot_exceed_provider_count(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=(),
                provider_count=1,
                successful_provider_count=2,
            )

    def test_bool_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=(),
                provider_count=True,
                successful_provider_count=0,
            )

        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=_graph(),
                errors=(),
                provider_count=1,
                successful_provider_count=False,
            )

    def test_errors_length_must_match_failed_count(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.PARTIAL,
                graph=_graph(),
                errors=(),
                provider_count=2,
                successful_provider_count=1,
            )

    def test_status_must_match_statistics(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.FAILED,
                graph=_graph(),
                errors=(),
                provider_count=1,
                successful_provider_count=1,
            )

    def test_graph_must_be_resource_graph(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.SUCCESS,
                graph=object(),
                errors=(),
                provider_count=0,
                successful_provider_count=0,
            )

    def test_errors_must_contain_provider_errors(self) -> None:
        with self.assertRaises(ValueError):
            TopologyResult(
                status=TopologyStatus.FAILED,
                graph=_graph(),
                errors=(object(),),
                provider_count=1,
                successful_provider_count=0,
            )


def _graph(*relations: ResourceRelation):
    builder = ResourceGraphBuilder()
    builder.add_resources(
        [
            Resource("service:api", "service", "api", "active"),
            Resource("database:main", "database", "main", "active"),
        ]
    )
    builder.add_relations(relations)
    return builder.build()


if __name__ == "__main__":
    unittest.main()

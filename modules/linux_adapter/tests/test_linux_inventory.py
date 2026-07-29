from __future__ import annotations

import copy
import unittest

from zorix_linux_adapter.errors import LinuxConfigurationError
from zorix_linux_adapter.inventory import (
    parse_os_release,
    parse_systemctl_services,
    services_to_resources,
    validate_target,
)


class LinuxInventoryTest(unittest.TestCase):
    def test_valid_target_is_accepted_and_stripped(self) -> None:
        self.assertEqual(validate_target(" tandem-01_db.example "), "tandem-01_db.example")

    def test_invalid_targets_are_rejected(self) -> None:
        invalid_targets = [
            "",
            " ",
            "bad target",
            "bad/target",
            "bad;target",
            "-target",
            "a" * 129,
        ]

        for target in invalid_targets:
            with self.subTest(target=target):
                with self.assertRaises(LinuxConfigurationError):
                    validate_target(target)

    def test_parse_os_release_handles_values_comments_and_malformed_lines(self) -> None:
        output = (
            "# comment\n"
            "ID=ubuntu\n"
            "NAME=\"Ubuntu\"\n"
            "PRETTY_NAME='Ubuntu 24.04 LTS'\n"
            "VERSION_ID=\"24.04\"\n"
            "UNKNOWN=value\n"
            "malformed\n"
        )
        original = str(output)

        values = parse_os_release(output)

        self.assertEqual(values["ID"], "ubuntu")
        self.assertEqual(values["NAME"], "Ubuntu")
        self.assertEqual(values["PRETTY_NAME"], "Ubuntu 24.04 LTS")
        self.assertEqual(values["VERSION_ID"], "24.04")
        self.assertEqual(values["UNKNOWN"], "value")
        self.assertEqual(output, original)

    def test_service_parser_handles_systemctl_output_defensively(self) -> None:
        output = (
            "nginx.service loaded active running A high performance web server\n"
            "tandem.service loaded active running\n"
            "● failed.service loaded failed failed Failed Service\n"
            "ssh.socket loaded active listening Socket\n"
            "malformed\n"
            "\n"
            "nginx.service loaded inactive dead Duplicate should be ignored later\n"
        )

        services = parse_systemctl_services(output)

        self.assertEqual(
            [service["unit"] for service in services],
            ["nginx.service", "tandem.service", "failed.service", "nginx.service"],
        )
        self.assertEqual(services[0]["description"], "A high performance web server")
        self.assertNotIn("description", services[1])
        self.assertEqual(services[2]["unit"], "failed.service")

    def test_service_markers_with_description_are_removed_before_split(self) -> None:
        for marker in ("●", "○", "×"):
            with self.subTest(marker=marker):
                services = parse_systemctl_services(
                    f"{marker} nginx.service loaded failed failed A high performance web server\n"
                )

                self.assertEqual(
                    services,
                    [
                        {
                            "unit": "nginx.service",
                            "load_state": "loaded",
                            "active_state": "failed",
                            "sub_state": "failed",
                            "description": "A high performance web server",
                        }
                    ],
                )

    def test_service_marker_without_description_is_parsed(self) -> None:
        services = parse_systemctl_services("● nginx.service loaded active running\n")

        self.assertEqual(
            services,
            [
                {
                    "unit": "nginx.service",
                    "load_state": "loaded",
                    "active_state": "active",
                    "sub_state": "running",
                }
            ],
        )

    def test_line_containing_only_marker_is_skipped(self) -> None:
        self.assertEqual(parse_systemctl_services("●\n○\n×\n"), [])

    def test_service_line_without_marker_still_parses_as_before(self) -> None:
        services = parse_systemctl_services(
            "nginx.service loaded active running A high performance web server\n"
        )

        self.assertEqual(services[0]["unit"], "nginx.service")
        self.assertEqual(services[0]["load_state"], "loaded")
        self.assertEqual(services[0]["active_state"], "active")
        self.assertEqual(services[0]["sub_state"], "running")
        self.assertEqual(services[0]["description"], "A high performance web server")

    def test_services_to_resources_deduplicates_and_preserves_first(self) -> None:
        output = (
            "nginx.service loaded active running First\n"
            "postgresql.service loaded inactive dead PostgreSQL\n"
            "nginx.service loaded failed failed Second\n"
        )
        original = copy.deepcopy(output)

        resources = services_to_resources(target="tandem", systemctl_output=output)

        self.assertEqual([resource.name for resource in resources], ["nginx.service", "postgresql.service"])
        self.assertEqual(resources[0].state, "active")
        self.assertEqual(resources[0].metadata["description"], "First")
        self.assertEqual(resources[0].id, "linux:service:tandem:nginx.service")
        self.assertEqual(resources[0].metadata["host_id"], "linux:host:tandem")
        self.assertEqual(output, original)


if __name__ == "__main__":
    unittest.main()

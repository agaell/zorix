from __future__ import annotations

import unittest

from zorix_linux_adapter.filesystems import filesystems_to_resources, parse_filesystems


class LinuxFilesystemsTest(unittest.TestCase):
    def test_parse_filesystems_regular_rows(self) -> None:
        filesystems = parse_filesystems(
            "Filesystem Type 1B-blocks Used Available Use% Mounted on\n"
            "/dev/vda1 ext4 53660876800 12000000000 39000000000 24% /\n"
            "/dev/mapper/data xfs 1000 200 800 20% /var/lib/data\n"
            "/dev/vda15 vfat 109422592 6500000 102000000 6% /boot/efi\n"
        )

        self.assertEqual([item.filesystem_type for item in filesystems], ["ext4", "xfs", "vfat"])
        self.assertEqual(filesystems[0].source, "/dev/vda1")
        self.assertEqual(filesystems[0].size_bytes, 53660876800)
        self.assertEqual(filesystems[0].used_bytes, 12000000000)
        self.assertEqual(filesystems[0].available_bytes, 39000000000)
        self.assertEqual(filesystems[0].usage_percent, 24)
        self.assertEqual(filesystems[0].mountpoint, "/")
        self.assertEqual(filesystems[1].mountpoint, "/var/lib/data")

    def test_parse_filesystems_skips_malformed_invalid_and_pseudo_rows(self) -> None:
        filesystems = parse_filesystems(
            "bad row\n"
            "/dev/vda1 ext4 invalid 1 1 1% /\n"
            "/dev/vda2 ext4 -1 1 1 1% /bad\n"
            "tmpfs tmpfs 1 1 1 1% /run\n"
            "snap squashfs 1 1 1 100% /snap/core\n"
            "overlay overlay 1 1 1 1% /overlay\n"
            "/dev/vda3 ext4 10 5 5 nope /ok\n"
        )

        self.assertEqual(len(filesystems), 1)
        self.assertEqual(filesystems[0].mountpoint, "/ok")
        self.assertIsNone(filesystems[0].usage_percent)

    def test_empty_output_returns_empty_list(self) -> None:
        self.assertEqual(parse_filesystems(""), [])

    def test_filesystem_resource_mapping_and_deduplication(self) -> None:
        resources = filesystems_to_resources(
            target="tandem",
            filesystems_output=(
                "/dev/vda1 ext4 100 20 80 20% /\n"
                "/dev/vda2 ext4 200 30 170 15% /boot/efi\n"
                "/dev/duplicate ext4 300 40 260 13% /\n"
            ),
        )

        self.assertEqual([resource.name for resource in resources], ["/", "/boot/efi"])
        self.assertEqual(resources[0].id, "linux:filesystem:tandem:%2F")
        self.assertEqual(resources[1].id, "linux:filesystem:tandem:%2Fboot%2Fefi")
        self.assertEqual(resources[0].type, "filesystem")
        self.assertEqual(resources[0].state, "mounted")
        self.assertEqual(resources[0].labels, {})
        self.assertEqual(resources[0].metadata["host_id"], "linux:host:tandem")
        self.assertEqual(resources[0].metadata["source"], "/dev/vda1")
        self.assertEqual(resources[0].metadata["filesystem_type"], "ext4")
        self.assertEqual(resources[0].metadata["size_bytes"], "100")
        self.assertEqual(resources[0].metadata["used_bytes"], "20")
        self.assertEqual(resources[0].metadata["available_bytes"], "80")
        self.assertEqual(resources[0].metadata["usage_percent"], "20")
        self.assertEqual(resources[0].metadata["mountpoint"], "/")


if __name__ == "__main__":
    unittest.main()

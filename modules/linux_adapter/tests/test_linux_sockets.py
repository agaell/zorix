from __future__ import annotations

import unittest

from zorix_linux_adapter.sockets import parse_listening_sockets, sockets_to_resources


class LinuxSocketsTest(unittest.TestCase):
    def test_parse_sockets_supported_endpoints(self) -> None:
        sockets = parse_listening_sockets(
            "tcp LISTEN 0 511 0.0.0.0:80 0.0.0.0:*\n"
            "tcp LISTEN 0 511 [::]:443 [::]:*\n"
            "tcp LISTEN 0 128 127.0.0.1:5432 0.0.0.0:*\n"
            "tcp LISTEN 0 128 [::1]:5432 [::]:*\n"
            "udp UNCONN 0 0 *:68 *:*\n"
            "udp UNCONN 0 0 127.0.0.53%lo:53 0.0.0.0:*\n"
            "udp UNCONN 0 0 [fe80::1%eth0]:5353 [::]:*\n"
        )

        self.assertEqual([socket.protocol for socket in sockets], ["tcp", "tcp", "tcp", "tcp", "udp", "udp", "udp"])
        self.assertEqual(sockets[0].bind_address, "0.0.0.0")
        self.assertEqual(sockets[0].port, 80)
        self.assertEqual(sockets[0].bind_scope, "all_interfaces")
        self.assertEqual(sockets[0].address_family, "ipv4")
        self.assertEqual(sockets[1].bind_address, "::")
        self.assertEqual(sockets[1].address_family, "ipv6")
        self.assertEqual(sockets[2].bind_scope, "loopback")
        self.assertEqual(sockets[4].bind_address, "*")
        self.assertEqual(sockets[4].address_family, "unknown")
        self.assertEqual(sockets[5].bind_scope, "specific_interface")
        self.assertEqual(sockets[6].bind_address, "fe80::1%eth0")
        self.assertEqual(sockets[6].bind_scope, "specific_interface")

    def test_parse_sockets_skips_invalid_rows(self) -> None:
        sockets = parse_listening_sockets(
            "raw LISTEN 0 0 0.0.0.0:1 0.0.0.0:*\n"
            "tcp LISTEN 0 0 malformed 0.0.0.0:*\n"
            "tcp LISTEN 0 0 0.0.0.0:nope 0.0.0.0:*\n"
            "tcp LISTEN 0 0 0.0.0.0:70000 0.0.0.0:*\n"
            "bad\n"
            "tcp LISTEN 0 0 10.0.0.1:8080 0.0.0.0:*\n"
        )

        self.assertEqual(len(sockets), 1)
        self.assertEqual(sockets[0].bind_address, "10.0.0.1")
        self.assertEqual(sockets[0].bind_scope, "specific_interface")

    def test_empty_output_returns_empty_list(self) -> None:
        self.assertEqual(parse_listening_sockets(""), [])

    def test_socket_resource_mapping_and_deduplication(self) -> None:
        resources = sockets_to_resources(
            target="tandem",
            sockets_output=(
                "tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n"
                "tcp LISTEN 0 511 [::]:443 [::]:*\n"
                "udp UNCONN 0 0 0.0.0.0:443 0.0.0.0:*\n"
                "tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n"
            ),
        )

        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0].id, "linux:socket:tandem:tcp:0.0.0.0:443")
        self.assertEqual(resources[1].id, "linux:socket:tandem:tcp:%3A%3A:443")
        self.assertEqual(resources[0].type, "socket")
        self.assertEqual(resources[0].name, "tcp://0.0.0.0:443")
        self.assertEqual(resources[1].name, "tcp://[::]:443")
        self.assertEqual(resources[0].state, "listening")
        self.assertEqual(resources[0].metadata["host_id"], "linux:host:tandem")
        self.assertEqual(resources[0].metadata["protocol"], "tcp")
        self.assertEqual(resources[0].metadata["socket_state"], "listen")
        self.assertEqual(resources[0].metadata["bind_address"], "0.0.0.0")
        self.assertEqual(resources[0].metadata["port"], "443")
        self.assertEqual(resources[0].metadata["bind_scope"], "all_interfaces")
        self.assertEqual(resources[0].metadata["address_family"], "ipv4")


if __name__ == "__main__":
    unittest.main()

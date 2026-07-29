from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from urllib.parse import quote

from zorix_core_model import Resource

from .inventory import host_resource_id


@dataclass(frozen=True)
class SocketSnapshot:
    protocol: str
    socket_state: str
    bind_address: str
    port: int
    bind_scope: str
    address_family: str


def parse_listening_sockets(output: str) -> list[SocketSnapshot]:
    sockets: list[SocketSnapshot] = []

    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) < 6:
            continue

        protocol = parts[0].strip().lower()
        if protocol not in ("tcp", "udp"):
            continue

        endpoint = _parse_endpoint(parts[4])
        if endpoint is None:
            continue

        bind_address, port = endpoint
        sockets.append(
            SocketSnapshot(
                protocol=protocol,
                socket_state=parts[1].strip().lower(),
                bind_address=bind_address,
                port=port,
                bind_scope=_bind_scope(bind_address),
                address_family=_address_family(bind_address),
            )
        )

    return sockets


def sockets_to_resources(
    *,
    target: str,
    sockets_output: str,
) -> list[Resource]:
    host_id = host_resource_id(target)
    resources: list[Resource] = []
    seen_resource_ids: set[str] = set()

    for socket in parse_listening_sockets(sockets_output):
        encoded_address = quote(socket.bind_address, safe="")
        resource_id = f"linux:socket:{target}:{socket.protocol}:{encoded_address}:{socket.port}"
        if resource_id in seen_resource_ids:
            continue

        seen_resource_ids.add(resource_id)
        resources.append(
            Resource(
                id=resource_id,
                type="socket",
                name=_socket_name(socket),
                state="listening",
                metadata={
                    "host_id": host_id,
                    "protocol": socket.protocol,
                    "socket_state": socket.socket_state,
                    "bind_address": socket.bind_address,
                    "port": str(socket.port),
                    "bind_scope": socket.bind_scope,
                    "address_family": socket.address_family,
                },
                labels={},
            )
        )

    return resources


def _parse_endpoint(endpoint: str) -> tuple[str, int] | None:
    if endpoint.startswith("["):
        close_index = endpoint.find("]")
        if close_index == -1 or close_index + 1 >= len(endpoint) or endpoint[close_index + 1] != ":":
            return None

        address = endpoint[1:close_index]
        port_text = endpoint[close_index + 2 :]
    else:
        if ":" not in endpoint:
            return None

        address, port_text = endpoint.rsplit(":", 1)

    if not address:
        return None

    port = _port(port_text)
    if port is None:
        return None

    return address, port


def _port(value: str) -> int | None:
    try:
        port = int(value)
    except ValueError:
        return None

    if port < 0 or port > 65535:
        return None

    return port


def _bind_scope(bind_address: str) -> str:
    if bind_address in ("0.0.0.0", "::", "*"):
        return "all_interfaces"

    if "%" in bind_address:
        return "specific_interface"

    parsed = _ip_address(bind_address)
    if parsed is None:
        return "unknown"

    if parsed.is_loopback:
        return "loopback"

    return "specific_interface"


def _address_family(bind_address: str) -> str:
    parsed = _ip_address(bind_address)
    if parsed is None:
        return "unknown"

    if isinstance(parsed, ipaddress.IPv4Address):
        return "ipv4"

    return "ipv6"


def _ip_address(bind_address: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if bind_address == "*":
        return None

    address = bind_address.split("%", 1)[0]
    try:
        return ipaddress.ip_address(address)
    except ValueError:
        return None


def _socket_name(socket: SocketSnapshot) -> str:
    address = socket.bind_address
    if ":" in address and address != "*":
        address = f"[{address}]"

    return f"{socket.protocol}://{address}:{socket.port}"

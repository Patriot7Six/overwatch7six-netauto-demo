"""Pytest configuration and shared fixtures for Overwatch7Six test suite."""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures"
TEMPLATE_DIR = REPO_ROOT / "golden_config" / "templates"


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """Return the repository root directory."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_dir() -> pathlib.Path:
    """Return the data/fixtures/ directory."""
    return FIXTURE_DIR


@pytest.fixture(scope="session")
def template_dir() -> pathlib.Path:
    """Return the golden_config/templates/ directory."""
    return TEMPLATE_DIR


@pytest.fixture(scope="session")
def devices_fixture() -> list[dict[str, Any]]:
    """Load the devices fixture YAML."""
    with open(FIXTURE_DIR / "devices.yml") as fh:
        data = yaml.safe_load(fh)
    return data.get("devices", [])


@pytest.fixture(scope="session")
def interfaces_fixture() -> list[dict[str, Any]]:
    """Load the interfaces fixture YAML."""
    with open(FIXTURE_DIR / "interfaces.yml") as fh:
        data = yaml.safe_load(fh)
    return data.get("interfaces", [])


@pytest.fixture(scope="session")
def ip_addresses_fixture() -> list[dict[str, Any]]:
    """Load the IP addresses fixture YAML."""
    with open(FIXTURE_DIR / "ip_addresses.yml") as fh:
        data = yaml.safe_load(fh)
    return data


@pytest.fixture(scope="session")
def vlans_fixture() -> list[dict[str, Any]]:
    """Load the VLANs fixture YAML."""
    with open(FIXTURE_DIR / "vlans.yml") as fh:
        data = yaml.safe_load(fh)
    return data.get("vlans", [])


class MockInterface:
    """Minimal mock of a Nautobot interface for template testing."""

    def __init__(
        self,
        name: str,
        description: str = "",
        mgmt_only: bool = False,
        iface_type: str = "1000base-t",
        ip_address: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.mgmt_only = mgmt_only
        self.type = iface_type
        self._ip = ip_address

    @property
    def ip_addresses(self) -> "MockQuerySet":
        """Return a MockQuerySet of IP addresses assigned to this interface."""
        if self._ip:
            return MockQuerySet([MockIPAddress(self._ip)])
        return MockQuerySet([])


class MockIPAddress:
    """Minimal mock of a Nautobot IP address for template testing."""

    def __init__(self, address: str) -> None:
        self.address = address

    def __str__(self) -> str:
        return self.address


class MockQuerySet:
    """Minimal mock of a Django QuerySet for template testing."""

    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def filter(self, **kwargs: Any) -> "MockQuerySet":
        """Filter items by attribute equality.

        Supports simple attr=value and attr__iexact=value lookups.
        """
        filtered = list(self._items)
        for key, value in kwargs.items():
            if "__" in key:
                attr, lookup = key.split("__", 1)
                if lookup == "iexact":
                    filtered = [
                        item for item in filtered
                        if str(getattr(item, attr, "")).lower() == str(value).lower()
                    ]
            else:
                filtered = [
                    item for item in filtered
                    if getattr(item, key, None) == value
                ]
        return MockQuerySet(filtered)

    def first(self) -> Any | None:
        return self._items[0] if self._items else None

    def exists(self) -> bool:
        return len(self._items) > 0

    def __iter__(self):
        return iter(self._items)


class MockDevice:
    """Minimal mock of a Nautobot Device object for Jinja2 template testing."""

    def __init__(
        self,
        name: str,
        role_slug: str,
        location_name: str = "HQ-TX-01",
        primary_ip4: str = "192.0.2.10/24",
        interfaces: list[MockInterface] | None = None,
    ) -> None:
        self.name = name
        self.role = MockRole(role_slug)
        self.location = MockLocation(location_name)
        self.primary_ip4 = MockIPAddress(primary_ip4)
        self._interfaces = interfaces or []

    @property
    def interfaces(self) -> MockQuerySet:
        return MockQuerySet(self._interfaces)


class MockRole:
    """Mock Nautobot Role."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.name = slug

    def __str__(self) -> str:
        return self.name


class MockLocation:
    """Mock Nautobot Location."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name


@pytest.fixture
def mock_rtr1() -> MockDevice:
    """Return a mock rtr1 device for template rendering tests."""
    lo_iface = MockInterface(
        "Loopback0", description="Router-id", ip_address="10.255.255.1/32", iface_type="virtual"
    )
    eth1 = MockInterface("Ethernet1", description="DIST1:Et1", ip_address="10.0.0.0/31")
    mgmt = MockInterface("Management0", description="OOB Management", mgmt_only=True)
    return MockDevice(
        name="rtr1",
        role_slug="edge",
        primary_ip4="192.0.2.10/24",
        interfaces=[lo_iface, eth1, mgmt],
    )


@pytest.fixture
def mock_dist1() -> MockDevice:
    """Return a mock dist1 device for template rendering tests."""
    lo_iface = MockInterface(
        "Loopback0", ip_address="10.255.255.2/32", iface_type="virtual"
    )
    eth1 = MockInterface("Ethernet1", description="RTR1:Et1", ip_address="10.0.0.1/31")
    eth2 = MockInterface("Ethernet2", description="ACC1:Et1", ip_address="10.0.0.2/31")
    eth3 = MockInterface("Ethernet3", description="ACC2:Et1", ip_address="10.0.0.4/31")
    mgmt = MockInterface("Management0", mgmt_only=True)
    return MockDevice(
        name="dist1",
        role_slug="distribution",
        primary_ip4="192.0.2.11/24",
        interfaces=[lo_iface, eth1, eth2, eth3, mgmt],
    )


@pytest.fixture
def mock_acc1() -> MockDevice:
    """Return a mock acc1 device for template rendering tests."""
    lo_iface = MockInterface(
        "Loopback0", ip_address="10.255.255.3/32", iface_type="virtual"
    )
    eth1 = MockInterface("Ethernet1", description="DIST1:Et2", ip_address="10.0.0.3/31")
    eth2 = MockInterface("Ethernet2", description="ACCESS:Data")
    eth3 = MockInterface("Ethernet3", description="ACCESS:Voice")
    eth4 = MockInterface("Ethernet4", description="ACCESS:Guest")
    mgmt = MockInterface("Management0", mgmt_only=True)
    return MockDevice(
        name="acc1",
        role_slug="access",
        primary_ip4="192.0.2.12/24",
        interfaces=[lo_iface, eth1, eth2, eth3, eth4, mgmt],
    )


@pytest.fixture
def mock_acc2() -> MockDevice:
    """Return a mock acc2 device for template rendering tests."""
    lo_iface = MockInterface(
        "Loopback0", ip_address="10.255.255.4/32", iface_type="virtual"
    )
    eth1 = MockInterface("Ethernet1", description="DIST1:Et3", ip_address="10.0.0.5/31")
    eth2 = MockInterface("Ethernet2", description="ACCESS:Data")
    eth3 = MockInterface("Ethernet3", description="ACCESS:Voice")
    eth4 = MockInterface("Ethernet4", description="ACCESS:Guest")
    mgmt = MockInterface("Management0", mgmt_only=True)
    return MockDevice(
        name="acc2",
        role_slug="access",
        primary_ip4="192.0.2.13/24",
        interfaces=[lo_iface, eth1, eth2, eth3, eth4, mgmt],
    )

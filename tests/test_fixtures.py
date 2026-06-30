"""Tests: YAML fixture schema sanity checks.

Validates that all fixture files are parseable YAML and contain the
minimum expected structure. Does not require a running Nautobot instance.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
import yaml


FIXTURE_DIR = pathlib.Path(__file__).parent.parent / "data" / "fixtures"
REQUIRED_FILES = [
    "sites.yml",
    "device_types.yml",
    "devices.yml",
    "interfaces.yml",
    "ip_addresses.yml",
    "vlans.yml",
]


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_fixture_file_exists(filename: str) -> None:
    """Every required fixture file must exist."""
    assert (FIXTURE_DIR / filename).exists(), f"Missing fixture: {filename}"


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_fixture_is_valid_yaml(filename: str) -> None:
    """Every fixture file must parse as valid YAML without errors."""
    content = (FIXTURE_DIR / filename).read_text()
    data = yaml.safe_load(content)
    assert data is not None, f"{filename} parsed to None (empty file?)"


def test_sites_has_locations() -> None:
    """sites.yml must define at least one location."""
    with open(FIXTURE_DIR / "sites.yml") as fh:
        data = yaml.safe_load(fh)
    locations = data.get("locations", [])
    assert len(locations) >= 1
    names = [l["name"] for l in locations]
    assert "HQ-TX-01" in names, "HQ-TX-01 location not found in sites.yml"


def test_devices_count() -> None:
    """devices.yml must define exactly 4 cEOS devices."""
    with open(FIXTURE_DIR / "devices.yml") as fh:
        data = yaml.safe_load(fh)
    devices = data.get("devices", [])
    assert len(devices) == 4, f"Expected 4 devices, got {len(devices)}"


def test_device_names() -> None:
    """All four expected device names must be present."""
    with open(FIXTURE_DIR / "devices.yml") as fh:
        data = yaml.safe_load(fh)
    names = {d["name"] for d in data.get("devices", [])}
    assert names == {"rtr1", "dist1", "acc1", "acc2"}


def test_device_roles_valid() -> None:
    """All devices must reference a valid role (edge, distribution, access)."""
    valid_roles = {"edge", "distribution", "access"}
    with open(FIXTURE_DIR / "devices.yml") as fh:
        data = yaml.safe_load(fh)
    for dev in data.get("devices", []):
        assert dev["role"] in valid_roles, f"{dev['name']} has invalid role: {dev['role']}"


def test_interfaces_reference_known_devices() -> None:
    """Every interface must reference a device that exists in devices.yml."""
    with open(FIXTURE_DIR / "devices.yml") as fh:
        dev_data = yaml.safe_load(fh)
    known_devices = {d["name"] for d in dev_data.get("devices", [])}

    with open(FIXTURE_DIR / "interfaces.yml") as fh:
        iface_data = yaml.safe_load(fh)
    for iface in iface_data.get("interfaces", []):
        assert iface["device"] in known_devices, (
            f"Interface {iface['name']} references unknown device: {iface['device']}"
        )


def test_ip_addresses_have_assignments() -> None:
    """IP addresses that are assigned must reference known devices."""
    with open(FIXTURE_DIR / "devices.yml") as fh:
        dev_data = yaml.safe_load(fh)
    known_devices = {d["name"] for d in dev_data.get("devices", [])}

    with open(FIXTURE_DIR / "ip_addresses.yml") as fh:
        ip_data = yaml.safe_load(fh)
    for ip in ip_data.get("ip_addresses", []):
        if "assigned_to" in ip:
            dev = ip["assigned_to"]["device"]
            assert dev in known_devices, f"IP {ip['address']} assigned to unknown device: {dev}"


def test_vlans_required_ids_present() -> None:
    """VLANs 10 (Data), 20 (Voice), 30 (Guest) must all be defined."""
    with open(FIXTURE_DIR / "vlans.yml") as fh:
        data = yaml.safe_load(fh)
    vids = {v["vid"] for v in data.get("vlans", [])}
    assert {10, 20, 30}.issubset(vids), f"Missing required VLANs. Found: {vids}"


def test_prefixes_cover_all_ranges() -> None:
    """ip_addresses.yml must define all required prefix ranges."""
    expected = {
        "10.255.255.0/24",
        "192.0.2.0/24",
        "10.0.0.0/24",
    }
    with open(FIXTURE_DIR / "ip_addresses.yml") as fh:
        data = yaml.safe_load(fh)
    defined = {p["prefix"] for p in data.get("prefixes", [])}
    missing = expected - defined
    assert not missing, f"Missing required prefixes: {missing}"

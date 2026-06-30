"""Seed Nautobot with HQ-TX-01 site, devices, IPAM, and VLANs.

Reads YAML fixtures from data/fixtures/ and creates or updates objects
via the pynautobot client. Safe to re-run — all upserts use get-or-create
patterns so duplicates are never created.

Nautobot REST API reference: https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/rest-api/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml
import pynautobot

FIXTURE_DIR = Path(__file__).parent / "fixtures"

NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "http://localhost:8080")
NAUTOBOT_TOKEN = os.getenv("NAUTOBOT_TOKEN", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")


def _load(filename: str) -> dict[str, Any]:
    """Load a YAML fixture file and return its contents."""
    with open(FIXTURE_DIR / filename) as fh:
        return yaml.safe_load(fh)


def get_or_create(endpoint: Any, lookup: dict[str, Any], payload: dict[str, Any]) -> tuple[Any, bool]:
    """Fetch an existing object or create a new one.

    Returns (object, created) where created is True if a new record was made.
    """
    existing = endpoint.get(**lookup)
    if existing:
        return existing, False
    created = endpoint.create(**payload)
    return created, True


def seed_location_types(nb: pynautobot.api) -> dict[str, Any]:
    """Create Region and Site location types if they don't exist."""
    data = _load("sites.yml")
    lt_map: dict[str, Any] = {}

    for lt in data.get("location_types", []):
        parent_id = lt_map[lt["parent"]].id if "parent" in lt else None
        payload = {"name": lt["name"], "nestable": lt.get("nestable", False)}
        if parent_id:
            payload["parent"] = parent_id
        obj, created = get_or_create(
            nb.dcim.location_types,
            {"name": lt["name"]},
            payload,
        )
        lt_map[lt["name"]] = obj
        print(f"  location_type {'[+]' if created else '[ ]'} {lt['name']}")

    return lt_map


def seed_locations(nb: pynautobot.api, lt_map: dict[str, Any]) -> dict[str, Any]:
    """Create Region and Site locations."""
    data = _load("sites.yml")
    loc_map: dict[str, Any] = {}

    for loc in data.get("locations", []):
        status = nb.extras.statuses.get(name=loc["status"])
        payload: dict[str, Any] = {
            "name": loc["name"],
            "location_type": lt_map[loc["location_type"]].id,
            "status": status.id,
        }
        if "parent" in loc:
            payload["parent"] = loc_map[loc["parent"]].id
        for field in ("description", "physical_address", "time_zone", "contact_name", "contact_email"):
            if field in loc:
                payload[field] = loc[field]

        obj, created = get_or_create(
            nb.dcim.locations,
            {"name": loc["name"]},
            payload,
        )
        loc_map[loc["name"]] = obj
        print(f"  location {'[+]' if created else '[ ]'} {loc['name']}")

    return loc_map


def seed_manufacturers_and_device_types(nb: pynautobot.api) -> dict[str, Any]:
    """Create manufacturer and device type records."""
    data = _load("device_types.yml")
    dt_map: dict[str, Any] = {}

    for mfr in data.get("manufacturers", []):
        obj, created = get_or_create(
            nb.dcim.manufacturers,
            {"name": mfr["name"]},
            mfr,
        )
        print(f"  manufacturer {'[+]' if created else '[ ]'} {mfr['name']}")

    for dt in data.get("device_types", []):
        mfr = nb.dcim.manufacturers.get(name=dt["manufacturer"])
        payload = {
            "manufacturer": mfr.id,
            "model": dt["model"],
            "slug": dt["slug"],
            "u_height": dt.get("u_height", 1),
            "is_full_depth": dt.get("is_full_depth", True),
        }
        obj, created = get_or_create(
            nb.dcim.device_types,
            {"model": dt["model"]},
            payload,
        )
        dt_map[dt["model"]] = obj
        print(f"  device_type {'[+]' if created else '[ ]'} {dt['model']}")

    return dt_map


def seed_roles(nb: pynautobot.api) -> dict[str, Any]:
    """Create device roles."""
    data = _load("device_types.yml")
    role_map: dict[str, Any] = {}

    for role in data.get("roles", []):
        obj, created = get_or_create(
            nb.extras.roles,
            {"name": role["name"]},
            role,
        )
        role_map[role["name"]] = obj
        print(f"  role {'[+]' if created else '[ ]'} {role['name']}")

    return role_map


def seed_platforms(nb: pynautobot.api) -> dict[str, Any]:
    """Create platform records (EOS + NAPALM driver)."""
    data = _load("devices.yml")
    plat_map: dict[str, Any] = {}

    for plat in data.get("platforms", []):
        mfr = nb.dcim.manufacturers.get(name=plat.get("manufacturer", "Arista Networks"))
        payload = {
            "name": plat["name"],
            "slug": plat["slug"],
            "manufacturer": mfr.id if mfr else None,
            "napalm_driver": plat.get("napalm_driver", ""),
        }
        obj, created = get_or_create(
            nb.dcim.platforms,
            {"name": plat["name"]},
            payload,
        )
        plat_map[plat["name"]] = obj
        print(f"  platform {'[+]' if created else '[ ]'} {plat['name']}")

    return plat_map


def seed_devices(
    nb: pynautobot.api,
    loc_map: dict[str, Any],
    dt_map: dict[str, Any],
    role_map: dict[str, Any],
    plat_map: dict[str, Any],
) -> dict[str, Any]:
    """Create device records."""
    data = _load("devices.yml")
    dev_map: dict[str, Any] = {}

    status = nb.extras.statuses.get(name="Active")

    for dev in data.get("devices", []):
        dt = dt_map.get(dev["device_type"]) or nb.dcim.device_types.get(slug=dev["device_type"])
        role = role_map.get(dev["role"]) or nb.extras.roles.get(name=dev["role"])
        location = loc_map.get(dev["location"]) or nb.dcim.locations.get(name=dev["location"])
        platform = plat_map.get(dev.get("platform", "")) or nb.dcim.platforms.get(slug=dev.get("platform", ""))

        payload: dict[str, Any] = {
            "name": dev["name"],
            "device_type": dt.id,
            "role": role.id,
            "location": location.id,
            "status": status.id,
        }
        if platform:
            payload["platform"] = platform.id
        if "comments" in dev:
            payload["comments"] = dev["comments"]

        obj, created = get_or_create(
            nb.dcim.devices,
            {"name": dev["name"]},
            payload,
        )
        dev_map[dev["name"]] = obj
        print(f"  device {'[+]' if created else '[ ]'} {dev['name']}")

    return dev_map


def seed_interfaces(nb: pynautobot.api, dev_map: dict[str, Any]) -> None:
    """Create interface records for all devices."""
    data = _load("interfaces.yml")
    status = nb.extras.statuses.get(name="Active")

    for iface in data.get("interfaces", []):
        dev = dev_map.get(iface["device"]) or nb.dcim.devices.get(name=iface["device"])
        payload: dict[str, Any] = {
            "device": dev.id,
            "name": iface["name"],
            "type": iface["type"],
            "status": status.id,
        }
        if "description" in iface:
            payload["description"] = iface["description"]
        if iface.get("mgmt_only"):
            payload["mgmt_only"] = True

        obj, created = get_or_create(
            nb.dcim.interfaces,
            {"device_id": dev.id, "name": iface["name"]},
            payload,
        )
        print(f"  interface {'[+]' if created else '[ ]'} {iface['device']}:{iface['name']}")


def seed_prefixes(nb: pynautobot.api) -> None:
    """Create IP prefix records."""
    data = _load("ip_addresses.yml")
    status = nb.extras.statuses.get(name="Active")

    for pfx in data.get("prefixes", []):
        namespace = nb.ipam.namespaces.get(name=pfx.get("namespace", "Global"))
        payload: dict[str, Any] = {
            "prefix": pfx["prefix"],
            "namespace": namespace.id,
            "status": status.id,
            "type": pfx.get("type", "network"),
        }
        if "description" in pfx:
            payload["description"] = pfx["description"]

        obj, created = get_or_create(
            nb.ipam.prefixes,
            {"prefix": pfx["prefix"], "namespace": namespace.id},
            payload,
        )
        print(f"  prefix {'[+]' if created else '[ ]'} {pfx['prefix']}")


def seed_ip_addresses(nb: pynautobot.api, dev_map: dict[str, Any]) -> None:
    """Create IP addresses and assign them to device interfaces."""
    data = _load("ip_addresses.yml")
    status = nb.extras.statuses.get(name="Active")
    namespace = nb.ipam.namespaces.get(name="Global")

    for ip_data in data.get("ip_addresses", []):
        payload: dict[str, Any] = {
            "address": ip_data["address"],
            "namespace": namespace.id,
            "status": status.id,
        }
        if "description" in ip_data:
            payload["description"] = ip_data["description"]
        if "role" in ip_data:
            payload["role"] = ip_data["role"].lower().replace(" ", "-")

        obj, created = get_or_create(
            nb.ipam.ip_addresses,
            {"address": ip_data["address"], "parent__namespace": namespace.id},
            payload,
        )
        print(f"  ip_address {'[+]' if created else '[ ]'} {ip_data['address']}")

        # Assign to device interface
        if "assigned_to" in ip_data:
            assign = ip_data["assigned_to"]
            dev = dev_map.get(assign["device"]) or nb.dcim.devices.get(name=assign["device"])
            iface = nb.dcim.interfaces.get(device_id=dev.id, name=assign["interface"])
            if iface:
                # Create interface IP assignment
                existing_assign = nb.ipam.ip_address_to_interface.get(
                    ip_address=obj.id, interface=iface.id
                )
                if not existing_assign:
                    nb.ipam.ip_address_to_interface.create(
                        ip_address=obj.id,
                        interface=iface.id,
                    )
                    print(f"    assigned {ip_data['address']} -> {assign['device']}:{assign['interface']}")


def seed_primary_ips(nb: pynautobot.api, dev_map: dict[str, Any]) -> None:
    """Set primary IPv4 on each device (management IP)."""
    data = _load("devices.yml")
    namespace = nb.ipam.namespaces.get(name="Global")

    for dev_data in data.get("devices", []):
        if "primary_ip4" not in dev_data:
            continue
        dev = dev_map.get(dev_data["name"]) or nb.dcim.devices.get(name=dev_data["name"])
        ip = nb.ipam.ip_addresses.get(
            address=dev_data["primary_ip4"],
            parent__namespace=namespace.id,
        )
        if ip and dev:
            nb.dcim.devices.get(name=dev_data["name"]).update({"primary_ip4": ip.id})
            print(f"  primary_ip4 set: {dev_data['name']} -> {dev_data['primary_ip4']}")


def seed_vlans(nb: pynautobot.api, loc_map: dict[str, Any]) -> None:
    """Create VLAN groups and VLANs."""
    data = _load("vlans.yml")
    status = nb.extras.statuses.get(name="Active")
    vg_map: dict[str, Any] = {}

    for vg in data.get("vlan_groups", []):
        location = loc_map.get(vg["location"]) or nb.dcim.locations.get(name=vg["location"])
        payload: dict[str, Any] = {
            "name": vg["name"],
            "location": location.id,
        }
        if "description" in vg:
            payload["description"] = vg["description"]
        obj, created = get_or_create(
            nb.ipam.vlan_groups,
            {"name": vg["name"]},
            payload,
        )
        vg_map[vg["name"]] = obj
        print(f"  vlan_group {'[+]' if created else '[ ]'} {vg['name']}")

    for vlan in data.get("vlans", []):
        location = loc_map.get(vlan["location"]) or nb.dcim.locations.get(name=vlan["location"])
        vg = vg_map.get(vlan.get("vlan_group", ""))
        payload: dict[str, Any] = {
            "vid": vlan["vid"],
            "name": vlan["name"],
            "status": status.id,
            "location": location.id,
        }
        if vg:
            payload["vlan_group"] = vg.id
        if "description" in vlan:
            payload["description"] = vlan["description"]

        obj, created = get_or_create(
            nb.ipam.vlans,
            {"vid": vlan["vid"], "location": location.id},
            payload,
        )
        print(f"  vlan {'[+]' if created else '[ ]'} {vlan['vid']} {vlan['name']}")


def main() -> None:
    """Run the full SoT seed sequence."""
    print(f"Connecting to Nautobot at {NAUTOBOT_URL}")
    nb = pynautobot.api(NAUTOBOT_URL, token=NAUTOBOT_TOKEN)

    # Verify connectivity
    try:
        nb.dcim.devices.count()
    except Exception as exc:
        print(f"ERROR: Cannot reach Nautobot at {NAUTOBOT_URL}: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n--- Location Types ---")
    lt_map = seed_location_types(nb)

    print("\n--- Locations ---")
    loc_map = seed_locations(nb, lt_map)

    print("\n--- Manufacturers & Device Types ---")
    dt_map = seed_manufacturers_and_device_types(nb)

    print("\n--- Roles ---")
    role_map = seed_roles(nb)

    print("\n--- Platforms ---")
    plat_map = seed_platforms(nb)

    print("\n--- Devices ---")
    dev_map = seed_devices(nb, loc_map, dt_map, role_map, plat_map)

    print("\n--- Interfaces ---")
    seed_interfaces(nb, dev_map)

    print("\n--- Prefixes ---")
    seed_prefixes(nb)

    print("\n--- IP Addresses ---")
    seed_ip_addresses(nb, dev_map)

    print("\n--- Primary IPs ---")
    seed_primary_ips(nb, dev_map)

    print("\n--- VLANs ---")
    seed_vlans(nb, loc_map)

    print("\n✓ SoT seed complete.")


if __name__ == "__main__":
    main()

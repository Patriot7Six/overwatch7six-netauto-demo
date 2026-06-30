"""Tests: render every Jinja2 template against mock fixtures.

Verifies that all role templates and partials render without raising
exceptions and meet minimum line count thresholds. Does not require
a running Nautobot instance — uses conftest.py mock objects.

Minimum line counts ensure the templates aren't accidentally returning
empty output after a refactor.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader, Undefined

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "golden_config" / "templates"

# Minimum non-blank lines expected per rendered role template
ROLE_MIN_LINES: dict[str, int] = {
    "edge": 30,
    "distribution": 30,
    "access": 30,
}


def _make_env() -> Environment:
    """Return a Jinja2 Environment pointed at golden_config/templates/."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=Undefined,
    )


def _count_non_blank(text: str) -> int:
    """Return the number of non-blank lines in rendered output."""
    return sum(1 for line in text.splitlines() if line.strip())


@pytest.mark.parametrize(
    "role,fixture_name",
    [
        ("edge", "mock_rtr1"),
        ("distribution", "mock_dist1"),
        ("access", "mock_acc1"),
        ("access", "mock_acc2"),
    ],
)
def test_role_template_renders(role: str, fixture_name: str, request: pytest.FixtureRequest) -> None:
    """Each role template must render without exceptions."""
    device = request.getfixturevalue(fixture_name)
    env = _make_env()
    template = env.get_template(f"roles/{role}.j2")
    rendered = template.render(obj=device)
    assert rendered, f"roles/{role}.j2 rendered empty output for {fixture_name}"


@pytest.mark.parametrize(
    "role,fixture_name",
    [
        ("edge", "mock_rtr1"),
        ("distribution", "mock_dist1"),
        ("access", "mock_acc1"),
    ],
)
def test_role_template_min_lines(role: str, fixture_name: str, request: pytest.FixtureRequest) -> None:
    """Each role template must produce at least ROLE_MIN_LINES non-blank lines."""
    device = request.getfixturevalue(fixture_name)
    env = _make_env()
    template = env.get_template(f"roles/{role}.j2")
    rendered = template.render(obj=device)
    count = _count_non_blank(rendered)
    minimum = ROLE_MIN_LINES[role]
    assert count >= minimum, (
        f"roles/{role}.j2 rendered only {count} non-blank lines (minimum: {minimum})"
    )


def test_edge_template_contains_hostname(mock_rtr1: Any) -> None:
    """Edge template must include the device hostname."""
    env = _make_env()
    rendered = env.get_template("roles/edge.j2").render(obj=mock_rtr1)
    assert "hostname rtr1" in rendered


def test_distribution_template_has_vlan_svids(mock_dist1: Any) -> None:
    """Distribution template must include VLAN SVI definitions."""
    env = _make_env()
    rendered = env.get_template("roles/distribution.j2").render(obj=mock_dist1)
    assert "interface Vlan10" in rendered
    assert "interface Vlan20" in rendered
    assert "interface Vlan30" in rendered


def test_access_template_has_vlans(mock_acc1: Any) -> None:
    """Access template must include all three user VLANs."""
    env = _make_env()
    rendered = env.get_template("roles/access.j2").render(obj=mock_acc1)
    assert "vlan 10" in rendered
    assert "vlan 20" in rendered
    assert "vlan 30" in rendered


def test_all_templates_contain_snmpv3(
    mock_rtr1: Any, mock_dist1: Any, mock_acc1: Any
) -> None:
    """Every role template must include SNMPv3 configuration (CM-6 requirement)."""
    env = _make_env()
    for role, device in [("edge", mock_rtr1), ("distribution", mock_dist1), ("access", mock_acc1)]:
        rendered = env.get_template(f"roles/{role}.j2").render(obj=device)
        assert "snmp-server group OW7SIX-GRP v3 priv" in rendered, (
            f"roles/{role}.j2 missing SNMPv3 group config"
        )
        assert "OW7SIX-USER" in rendered, (
            f"roles/{role}.j2 missing SNMPv3 user config"
        )


def test_all_templates_contain_banner(
    mock_rtr1: Any, mock_dist1: Any, mock_acc1: Any
) -> None:
    """Every role template must include the CUI access banner (AC-8 requirement)."""
    env = _make_env()
    for role, device in [("edge", mock_rtr1), ("distribution", mock_dist1), ("access", mock_acc1)]:
        rendered = env.get_template(f"roles/{role}.j2").render(obj=device)
        assert "AUTHORIZED ACCESS ONLY" in rendered, (
            f"roles/{role}.j2 missing CUI access banner"
        )


def test_all_templates_contain_logging(
    mock_rtr1: Any, mock_dist1: Any, mock_acc1: Any
) -> None:
    """Every role template must include syslog configuration (AU-2 requirement)."""
    env = _make_env()
    for role, device in [("edge", mock_rtr1), ("distribution", mock_dist1), ("access", mock_acc1)]:
        rendered = env.get_template(f"roles/{role}.j2").render(obj=device)
        assert "logging host" in rendered, (
            f"roles/{role}.j2 missing syslog configuration"
        )


def test_all_templates_contain_aaa(
    mock_rtr1: Any, mock_dist1: Any, mock_acc1: Any
) -> None:
    """Every role template must include AAA configuration (IA-2 requirement)."""
    env = _make_env()
    for role, device in [("edge", mock_rtr1), ("distribution", mock_dist1), ("access", mock_acc1)]:
        rendered = env.get_template(f"roles/{role}.j2").render(obj=device)
        assert "aaa authentication login default local" in rendered, (
            f"roles/{role}.j2 missing AAA configuration"
        )


def test_all_templates_contain_ntp(
    mock_rtr1: Any, mock_dist1: Any, mock_acc1: Any
) -> None:
    """Every role template must include NTP configuration (AU-8 requirement)."""
    env = _make_env()
    for role, device in [("edge", mock_rtr1), ("distribution", mock_dist1), ("access", mock_acc1)]:
        rendered = env.get_template(f"roles/{role}.j2").render(obj=device)
        assert "ntp server" in rendered, (
            f"roles/{role}.j2 missing NTP configuration"
        )


def test_partial_snmp_renders_standalone() -> None:
    """_snmp.j2 partial must render its macro without a device context."""
    env = _make_env()
    # Render the partial macro directly
    template_str = (
        "{% from 'partials/_snmp.j2' import snmp_config %}"
        "{{ snmp_config('f5717f001a2b3c4d') }}"
    )
    rendered = env.from_string(template_str).render()
    assert "snmp-server group OW7SIX-GRP v3 priv" in rendered


def test_partial_logging_renders_standalone() -> None:
    """_logging.j2 partial must render its macro without a device context."""
    env = _make_env()
    template_str = (
        "{% from 'partials/_logging.j2' import logging_config %}"
        "{{ logging_config() }}"
    )
    rendered = env.from_string(template_str).render()
    assert "logging host 192.0.2.2 514" in rendered
    assert "logging on" in rendered


def test_partial_banner_renders_standalone() -> None:
    """_banner.j2 partial must render its macro without a device context."""
    env = _make_env()
    template_str = (
        "{% from 'partials/_banner.j2' import banner_config %}"
        "{{ banner_config() }}"
    )
    rendered = env.from_string(template_str).render()
    assert "AUTHORIZED ACCESS ONLY" in rendered


def test_partial_ntp_renders_standalone() -> None:
    """_ntp.j2 partial must render its macro without a device context."""
    env = _make_env()
    template_str = (
        "{% from 'partials/_ntp.j2' import ntp_config %}"
        "{{ ntp_config() }}"
    )
    rendered = env.from_string(template_str).render()
    assert "ntp server 192.0.2.1" in rendered

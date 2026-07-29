"""Tests for address-related entity extraction."""

from __future__ import annotations

from entity_extractor import collect_alert_addresses, extract_entities


def test_collect_alert_addresses_from_wallet_and_phone() -> None:
    text = (
        "Wire 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0 then call +1-555-014-8821. "
        "Meet at 214 Harbor Wharf Rd."
    )
    addresses = collect_alert_addresses(text)
    assert any(item.startswith("wallet:") for item in addresses)
    assert any(item.startswith("phone:") for item in addresses)
    assert any(item.startswith("address:") for item in addresses)


def test_wallet_extractor_deduplicates() -> None:
    wallet = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
    matches = extract_entities(f"pay {wallet} and confirm {wallet}")
    wallet_matches = [match for match in matches if match.entity_type == "wallet"]
    assert len(wallet_matches) == 1

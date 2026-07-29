"""Tests for simulation-mode alert logging."""

from __future__ import annotations

from simulation_alerts import (
    reset_simulation_alerts,
    send_simulation_address_alerts,
    send_simulation_test_alert,
    simulation_alert_status,
)
from telegram_alerts import AlertMessage


def test_simulation_alert_flow() -> None:
    reset_simulation_alerts()
    status = simulation_alert_status()
    assert status["ready"] is True
    assert status["simulation_mode"] is True

    test = send_simulation_test_alert()
    assert test.ok is True
    assert simulation_alert_status()["alerts_sent"] == 1

    items = [
        AlertMessage(
            chat_name="Sim Channel",
            message_id=42,
            sender="user1",
            text="contact me",
            categories=("narcotics",),
            keywords=("contact",),
            addresses=("555-0100",),
            alert_key="sim:42",
        )
    ]
    sent = send_simulation_address_alerts(items)
    assert sent.ok is True
    assert simulation_alert_status()["alerts_sent"] == 2

    duplicate = send_simulation_address_alerts(items)
    assert duplicate.ok is False
    assert duplicate.detail == "No new address alerts to send"

    reset_simulation_alerts()
    assert simulation_alert_status()["alerts_sent"] == 0

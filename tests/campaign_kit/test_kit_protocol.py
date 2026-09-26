"""registration/protocol.json: the constants block and constant lookups refuse what is not
registered, so confirm.py cannot run on a value the registration does not hold."""

from __future__ import annotations

import json

import pytest

from bio_lab.campaign_kit import protocol
from bio_lab.campaign_kit.common import KitError
from conftest import write


def campaign_with(tmp_path, body) -> object:
    text = body if isinstance(body, str) else json.dumps(body)
    write(tmp_path / "registration" / "protocol.json", text)
    return tmp_path


def test_constants_are_read_from_the_registration(tmp_path):
    campaign = campaign_with(tmp_path, {"constants": {"ALPHA": 0.05, "MODE": "strict"}})
    constants = protocol.load_constants(campaign)
    assert constants == {"ALPHA": 0.05, "MODE": "strict"}
    constants["ALPHA"] = 1.0               # a copy: the caller cannot change the source
    assert protocol.constant(campaign, "ALPHA") == 0.05
    assert protocol.constant(str(campaign), "MODE") == "strict"


@pytest.mark.parametrize("body", [
    {},                                     # no constants block
    {"constants": {}},                      # an empty block
    {"constants": None},
    {"constants": [["ALPHA", 0.05]]},       # not an object
    {"constants": "ALPHA=0.05"},
])
def test_a_missing_or_empty_constants_block_is_refused(tmp_path, body):
    campaign = campaign_with(tmp_path, body)
    with pytest.raises(KitError, match="no nonempty \"constants\" object"):
        protocol.load_constants(campaign)
    with pytest.raises(KitError, match="no nonempty \"constants\" object"):
        protocol.constant(campaign, "ALPHA")


def test_an_unregistered_constant_is_refused(tmp_path):
    campaign = campaign_with(tmp_path, {"constants": {"ALPHA": 0.05}})
    with pytest.raises(KitError, match="constant BETA is not registered"):
        protocol.constant(campaign, "BETA")
    with pytest.raises(KitError, match="not registered"):
        protocol.constant(campaign, "alpha")      # names are case-sensitive


def test_a_missing_or_malformed_protocol_is_refused(tmp_path):
    with pytest.raises(KitError):
        protocol.load_constants(tmp_path)
    campaign = campaign_with(tmp_path, "{not json")
    with pytest.raises(KitError):
        protocol.load_constants(campaign)
    campaign = campaign_with(tmp_path, "[1, 2]")
    with pytest.raises(KitError):
        protocol.load_constants(campaign)

"""A fresh install can import the fal.ai SDK the production agent calls."""

import fal_client


def test_fal_client_sdk_is_installed():
    assert callable(fal_client.upload_file)
    assert callable(fal_client.subscribe)

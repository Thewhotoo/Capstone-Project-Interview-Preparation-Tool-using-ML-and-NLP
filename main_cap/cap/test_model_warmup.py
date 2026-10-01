"""
model_warmup.use_local_models_only: offline mode only when every model the app
will load is already downloaded -- including the trained Round 1 evaluator's
backbone when its weights file is installed.
"""

import os
import unittest
from unittest import mock

import model_warmup as mw


class TestUseLocalModelsOnly(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)

    def run_with(self, cached, weights_installed):
        with mock.patch.object(mw, "_is_cached", lambda m: m in cached), \
             mock.patch.object(mw.Path, "exists", lambda p: weights_installed if p == mw.TRAINED_WEIGHTS else False):
            return mw.use_local_models_only()

    def test_offline_when_everything_is_cached(self):
        self.assertTrue(self.run_with(set(mw.REQUIRED_MODELS) | {mw.TRAINED_BACKBONE}, weights_installed=True))
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")

    def test_stays_online_when_a_model_is_missing(self):
        self.assertFalse(self.run_with(set(mw.REQUIRED_MODELS[1:]), weights_installed=False))
        self.assertNotIn("HF_HUB_OFFLINE", os.environ)

    def test_weights_added_later_still_downloads_the_backbone(self):
        # ran once without the weights (backbone never downloaded), then installed them
        self.assertFalse(self.run_with(set(mw.REQUIRED_MODELS), weights_installed=True))

    def test_backbone_not_needed_without_weights(self):
        self.assertTrue(self.run_with(set(mw.REQUIRED_MODELS), weights_installed=False))

    def test_explicit_setting_is_respected(self):
        os.environ["HF_HUB_OFFLINE"] = "0"
        self.assertFalse(self.run_with(set(), weights_installed=False))


if __name__ == "__main__":
    unittest.main()

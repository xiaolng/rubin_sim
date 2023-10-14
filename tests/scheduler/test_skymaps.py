import unittest
import numpy as np
from rubin_sim.scheduler.utils import SkyAreaGenerator, SkyAreaGeneratorGalplane, EuclidOverlapFootprint


class TestSkyArea(unittest.TestCase):
    def setUp(self):
        self.nside = 32

    def test_skyareagenerator(self):
        # Just test that it sets up and returns maps
        s = SkyAreaGenerator(nside=self.nside)
        footprints, labels = s.return_maps()
        expected_labels = ["", "LMC_SMC", "bulge", "dusty_plane", "lowdust", "nes", "scp", "virgo"]
        self.assertEqual(set(np.unique(labels)), set(expected_labels))
        # Check that ratios in the low-dust wfd in r band are 1
        # This doesn't always have to be the case, but should be with defaults
        lowdust = np.where(labels == "lowdust")
        self.assertTrue(np.all(footprints["r"][lowdust] == 1))

    def test_skyareageneratorgalplane(self):
        # Just test that it sets up and returns maps
        s = SkyAreaGeneratorGalplane(nside=self.nside)
        footprints, labels = s.return_maps()
        expected_labels = ["", "LMC_SMC", "bulgy", "dusty_plane", "lowdust", "nes", "scp", "virgo"]
        self.assertEqual(set(np.unique(labels)), set(expected_labels))
        # Check that ratios in the low-dust wfd in r band are 1
        # This doesn't always have to be the case, but should be with defaults
        lowdust = np.where(labels == "lowdust")
        self.assertTrue(np.all(footprints["r"][lowdust] == 1))

    def test_euclidoverlapfootprint(self):
        # Just test that it sets up and returns maps
        s = EuclidOverlapFootprint(nside=self.nside)
        footprints, labels = s.return_maps()
        expected_labels = [
            "",
            "LMC_SMC",
            "bulgy",
            "dusty_plane",
            "lowdust",
            "nes",
            "scp",
            "virgo",
            "euclid_overlap",
        ]
        self.assertEqual(set(np.unique(labels)), set(expected_labels))
        # Check that ratios in the low-dust wfd in r band are 1
        # This doesn't always have to be the case, but should be with defaults
        lowdust = np.where(labels == "lowdust")
        self.assertTrue(np.all(footprints["r"][lowdust] == 1))


if __name__ == "__main__":
    unittest.main()

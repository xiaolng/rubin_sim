__all__ = ("PhotometricSelfCalUniformityMetric",)

import os
import numpy as np
from astropy.table import Table
import time
from scipy.stats import median_abs_deviation
import healpy as hp
import astropy.units as units
from astropy.coordinates import SkyCoord

from rubin_sim.maf.metrics import BaseMetric
from rubin_sim.selfcal import generate_catalog, OffsetSNR, LsqrSolver
from rubin_sim.selfcal.offsets import OffsetSys
from rubin_scheduler.utils import healbin
from rubin_scheduler.data import get_data_dir


def _match(arr1, arr2):
    st1 = np.argsort(arr1)
    sub1 = np.searchsorted(arr1, arr2, sorter=st1)
    if arr2.max() > arr1.max():
        bad = sub1 == arr1.size
        sub1[bad] = arr1.size - 1

    sub2, = np.where(arr1[st1[sub1]] == arr2)
    sub1 = st1[sub1[sub2]]

    return sub1, sub2


class PhotometricSelfCalUniformityMetric(BaseMetric):
    def __init__(self, nside_residual=128, highglat_cut=30.0, outlier_nsig=4.0, run_name="", write_map=True):
        cols = [
            "observationid",
            "fieldra",
            "fielddec",
            "fiveSigmaDepth",
            "rotSkyPos",
            "filter",
        ]
        super().__init__(col=cols, metric_name="photometricSelfCalUniformityMetric")

        filename = os.path.join(get_data_dir(), "maf", "monster_stars_uniformity_i15-18_sampled.parquet")
        self.stars = Table.read(filename)

        # We have to rename dec to decl for the selfcal code.
        if "dec" in self.stars.dtype.names:
            self.stars["decl"] = self.stars["dec"]

        self.stars = self.stars.as_array()

        self.nside_residual = nside_residual
        self.highglat_cut = highglat_cut
        self.outlier_nsig = outlier_nsig
        self.run_name = run_name
        self.write_map = write_map

        self.units = "mmag"

    def run(self, data_slice, slice_point=None):
        filter_name = data_slice["filter"][0]

        offsets = [OffsetSys(error_sys=0.03), OffsetSNR(lsst_filter=filter_name)]

        visits = np.zeros(
            len(data_slice),
            dtype=[
                ("observationId", "i8"),
                ("ra", "f8"),
                ("dec", "f8"),
                ("fiveSigmaDepth", "f8"),
                ("rotSkyPos", "f8"),
            ]
        )
        visits["observationId"] = data_slice["observationId"]
        visits["ra"] = data_slice["fieldRA"]
        visits["dec"] = data_slice["fieldDec"]
        visits["fiveSigmaDepth"] = data_slice["fiveSigmaDepth"]
        visits["rotSkyPos"] = data_slice["rotSkyPos"]

        good_stars = np.isfinite(self.stars[f"{filter_name}mag"])
        stars = self.stars[good_stars]

        observed_stars = generate_catalog(
            visits,
            stars,
            offsets=offsets,
            lsst_filter=filter_name,
            n_patches=16,
            verbose=False,
        )

        solver = LsqrSolver(observed_stars)

        print("Starting solver...")
        t0 = time.time()

        solver.run()
        fit_patches, fit_stars = solver.return_solution()

        t1 = time.time()
        dt = (t1-t0)/60.
        print("runtime= %.1f min" % dt)

        # Trim stars to the ones with solutions.
        a, b = _match(stars["id"], fit_stars["id"])
        stars_trimmed = stars[a]
        fit_stars_trimmed = fit_stars[b]

        # Residuals after fit, removing floating zeropoint
        resid = stars_trimmed[f'{filter_name}mag'] - fit_stars_trimmed['fit_mag']
        resid = resid - np.median(resid)

        resid_map = healbin(
            stars_trimmed["ra"],
            stars_trimmed["dec"],
            resid,
            self.nside_residual,
            reduce_func=np.median,
        )

        ipring, = np.where(resid_map > hp.UNSEEN)

        scatter_full = median_abs_deviation(resid_map[ipring], scale="normal")

        # Fraction of (4) sigma outliers.
        highscat = (np.abs(resid_map[ipring]) > self.outlier_nsig*scatter_full)
        outlier_frac_full = highscat.sum() / len(ipring)

        # Cut to high latitude
        ra, dec = hp.pix2ang(self.nside_residual, ipring, nest=False, lonlat=True)
        coords = SkyCoord(ra, dec, frame="icrs", unit="deg")
        b = coords.galactic.b.value

        high_glat = (np.abs(b) > self.highglat_cut)
        scatter_highglat = median_abs_deviation(resid_map[ipring[high_glat]], scale="normal")

        # Fraction of (4) sigma outliers.
        highscat = (np.abs(resid_map[ipring[high_glat]]) > self.outlier_nsig*scatter_highglat)
        outlier_frac_highglat = highscat.sum() / len(ipring)

        # Convert to mmag
        scatter_full = scatter_full * 1000.0
        scatter_highglat  = scatter_highglat * 1000.0

        result = {
            "scatter_full": scatter_full,
            "scatter_highglat": scatter_highglat,
            "outlier_frac_full": outlier_frac_full,
            "outlier_frac_highglat": outlier_frac_highglat,
        }

        # Write out the map for downstream visualization.
        if self.write_map:
            fname = f"monster_stars_{filter_name}_{self.run_name}.fits"
            if os.path.isfile(fname):
                print("Not overwriting existing map of name ", fname)
            else:
                print("Writing map ", fname)
                hp.write_map(f"monster_stars_{filter_name}_{self.run_name}.fits", resid_map)

        import IPython
        IPython.embed()
        return result

    def reduce_scatter_full(self, metric_value):
        return metric_value["scatter_full"]

    def reduce_scatter_highglat(self, metric_value):
        return metric_value["scatter_highglat"]

    def reduce_outlier_frac_full(self, metric_value):
        return metric_value["outlier_frac_full"]

    def reduce_outlier_frac_highglat(self, metric_value):
        return metric_value["outlier_frac_highglat"]

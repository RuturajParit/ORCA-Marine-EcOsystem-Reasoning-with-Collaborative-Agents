"""Copernicus Marine (free account) adapter for salinity, chlorophyll, pH, oxygen, biomass proxy.
Set CMEMS_USERNAME / CMEMS_PASSWORD. Dataset ids/variables can be overridden with
CMEMS_DS_<KEY> / CMEMS_VAR_<KEY> (e.g. CMEMS_DS_PH) if Copernicus renames products."""
import os

SPECS = {  # key: (dataset_id, variable)
    "salinity":    ("cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m", "so"),
    "chlorophyll": ("cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m", "chl"),
    "biomass":     ("cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m", "phyc"),
    "oxygen":      ("cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m", "o2"),
    "ph":          ("cmems_mod_glo_bgc-car_anfc_0.25deg_P1D-m", "ph"),
}
NOTES = {"biomass": "Phytoplankton carbon (phyc): a biomass PROXY, not a fish-stock estimate.",
         "chlorophyll": "Model analysis/forecast (daily). Not the INCOIS PFZ advisory."}


def spec(key):
    ds, var = SPECS[key]
    return os.getenv(f"CMEMS_DS_{key.upper()}", ds), os.getenv(f"CMEMS_VAR_{key.upper()}", var)


def fetch_layer(key, lats, lons, days):
    """Returns [len(days)][len(lats)][len(lons)] floats/None at the surface."""
    user, pw = os.getenv("CMEMS_USERNAME"), os.getenv("CMEMS_PASSWORD")
    if not (user and pw):
        raise RuntimeError("Set CMEMS_USERNAME and CMEMS_PASSWORD in .env (free account: data.marine.copernicus.eu)")
    try:
        import copernicusmarine as cm
    except ImportError:
        raise RuntimeError("pip install copernicusmarine xarray scipy")
    ds_id, var = spec(key)
    ds = cm.open_dataset(dataset_id=ds_id, variables=[var], username=user, password=pw,
                         minimum_latitude=min(lats) - 1, maximum_latitude=max(lats) + 1,
                         minimum_longitude=min(lons) - 1, maximum_longitude=max(lons) + 1,
                         minimum_depth=0, maximum_depth=2,
                         start_datetime=f"{days[0]}T00:00:00", end_datetime=f"{days[-1]}T23:59:59")
    da = ds[var]
    if "depth" in da.dims:
        da = da.isel(depth=0)
    da = da.interp(latitude=lats, longitude=lons)
    out = []
    for d in days:
        a = da.sel(time=d, method="nearest").load().values
        out.append([[None if x != x else float(x) for x in row] for row in a])
    return out

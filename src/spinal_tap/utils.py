"""Defines basic functions used by the Spinal Tap application."""

from typing import Any, Dict, Optional, Tuple

from spine.construct import BuildManager
from spine.io.core.read import HDF5Reader


def initialize_reader(file_path: str, use_run: bool = False) -> HDF5Reader:
    """Initialize the HDF5 reader.

    TODO: add option to read from LArCV files (more tricky)

    Parameters
    ----------
    file_path : str
        Path to the file to load
    use_run : bool
        If `True`, build the run map to fetch the entries by (run, subrun, event)

    Returns
    -------
    HDF5Reader
        File reader
    """
    return HDF5Reader(
        file_path.strip(), create_run_map=use_run, skip_unknown_attrs=True
    )


def load_data(reader: HDF5Reader, entry: int, mode: str, obj: str) -> Tuple[
    Dict[str, Any],
    Optional[Dict[str, str]],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    """Loads one entry from an HDF5 SPINE reconstruction file.

    Parameters
    ----------
    reader : HDF5Reader
        Path to the file reader
    entry : int
        Entry to load within the file
    mode : str
        Run mode (one of 'reco', 'truth' or 'both')
    obj : str
        Type of object to load

    Returns
    -------
    dict
        Data product dictionary
    dict
        Geometry configuration, if available in the file
    int
        Run number
    int
        Subrun number
    int
        Event number
    """
    # Load the entry as a dictionary
    data = reader.get(entry)

    # Initialize the builder
    builder = BuildManager(
        obj == "fragments",
        obj in ["particles", "interactions"],
        obj == "interactions",
        mode=mode,
    )

    # Process the entry through the builder
    builder(data)

    # Return geometry configuration if available
    geo = None
    if reader.cfg is not None:
        geo = reader.cfg.get("geo", None)

    # Return run info if available
    run, subrun, event = None, None, None
    if "run_info" in data:
        run_info = data["run_info"]
        run, subrun, event = run_info.run, run_info.subrun, run_info.event

    # Return
    return data, geo, run, subrun, event

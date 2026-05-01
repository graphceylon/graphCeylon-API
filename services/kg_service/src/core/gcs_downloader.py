"""GCS Downloader utility for the KG service.

Tries to fetch the latest version of each data file from the GCS bucket.
Falls back silently to the existing local file when GCS is not configured
or the download fails.

Actual GCS bucket layout (tourism-data bucket, confirmed):
  streamlit_attractions/<timestamp>/touristattractionsscraper_data.json
  streamlit_events/<timestamp>/lankaevents_<year>.json
  streamlit_holidays/<timestamp>/sri_lanka_holidays_<year>_all_months.json
  streamlit_hotels/<timestamp>/hotels_near_attractions.json
  tourism_news_weekly/<timestamp>/tourism_news.json
  sltda_projects_monthly/<timestamp>/sltda_projects.json
  streamlit_sub_attractions/<timestamp>/location_pois/<name>.json
  streamlit_train_schedule/<timestamp>/stations/railway_stations_enriched.json

Timestamps use the format YYYY-MM-DD_HH-MM-SS (e.g. 2026-03-04_23-38-50).
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
# Read GCS settings directly from env (no circular import with config)
# -----------------------------------------------------------------
_BUCKET: str = os.getenv("GCS_BUCKET_NAME", "")


def _get_client():
    """Return an initialised GCS client, or None if unavailable."""
    if not _BUCKET:
        return None
    try:
        from google.cloud import storage  # type: ignore
        return storage.Client()
    except Exception as exc:
        logger.debug("GCS client unavailable: %s", exc)
        return None


# -----------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------

def try_download_file(blob_path: str, local_path: str) -> bool:
    """Download a single blob to *local_path*.

    Args:
        blob_path: Full blob name inside the bucket (e.g.
                   ``tourism-pipeline/sltda/attractions/tourist_attractions.json``).
        local_path: Absolute local path where the file should be written.

    Returns:
        True on success, False on any failure.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        bucket = client.bucket(_BUCKET)
        blob = bucket.blob(blob_path)
        if not blob.exists():
            logger.debug("GCS blob not found: gs://%s/%s", _BUCKET, blob_path)
            return False
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path)
        logger.info("Downloaded gs://%s/%s → %s", _BUCKET, blob_path, local_path)
        return True
    except Exception as exc:
        logger.warning("GCS download failed for %s: %s", blob_path, exc)
        return False


def try_download_latest_in_prefix(
    prefix: str,
    local_path: str,
    pattern: Optional[str] = None,
) -> bool:
    """Download the most-recently-updated blob under *prefix* to *local_path*.

    Args:
        prefix:     Blob prefix to list (e.g. ``tourism-pipeline/sltda/events/``).
        local_path: Where to write the downloaded file.
        pattern:    Optional substring that the blob name must contain.

    Returns:
        True on success, False on any failure.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        bucket = client.bucket(_BUCKET)
        blobs = list(bucket.list_blobs(prefix=prefix))
        if pattern:
            blobs = [b for b in blobs if pattern in b.name]
        if not blobs:
            logger.debug("No blobs found under gs://%s/%s (pattern=%s)", _BUCKET, prefix, pattern)
            return False
        # Pick the most recently updated blob
        latest = max(blobs, key=lambda b: b.updated)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        latest.download_to_filename(local_path)
        logger.info(
            "Downloaded latest gs://%s/%s → %s", _BUCKET, latest.name, local_path
        )
        return True
    except Exception as exc:
        logger.warning("GCS prefix download failed for %s: %s", prefix, exc)
        return False


def try_download_directory(prefix: str, local_dir: str, suffix: str = ".json") -> bool:
    """Download all blobs under *prefix* that end with *suffix* into *local_dir*.

    Args:
        prefix:    Blob prefix (e.g. ``streamlit_sub_attractions/2026-03-04_23-02-42/location_pois/``).
        local_dir: Local directory to write files into.
        suffix:    File extension filter (default ``.json``).

    Returns:
        True if at least one file was downloaded, False otherwise.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        bucket = client.bucket(_BUCKET)
        blobs = [b for b in bucket.list_blobs(prefix=prefix) if b.name.endswith(suffix)]
        if not blobs:
            logger.debug("No blobs found under gs://%s/%s", _BUCKET, prefix)
            return False
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        downloaded = 0
        for blob in blobs:
            filename = Path(blob.name).name
            dest = Path(local_dir) / filename
            try:
                blob.download_to_filename(str(dest))
                downloaded += 1
            except Exception as exc:
                logger.warning("Failed to download %s: %s", blob.name, exc)
        logger.info(
            "Downloaded %d file(s) from gs://%s/%s → %s",
            downloaded, _BUCKET, prefix, local_dir,
        )
        return downloaded > 0
    except Exception as exc:
        logger.warning("GCS directory download failed for %s: %s", prefix, exc)
        return False


def try_download_latest_timestamped_directory(
    dag_prefix: str,
    subpath: Optional[str],
    local_dir: str,
    suffix: str = ".json",
) -> bool:
    """Download all files from the most-recent timestamped subfolder of a DAG prefix.

    The bucket layout for timestamped DAG uploads is:
      <dag_prefix>/<YYYY-MM-DD_HH-MM-SS>/<subpath>/<filename>   (subpath given)
      <dag_prefix>/<YYYY-MM-DD_HH-MM-SS>/<filename>              (subpath=None)

    This helper finds the latest timestamp folder and downloads all matching
    files from it (or its *subpath*) into *local_dir*.

    Args:
        dag_prefix: Root DAG folder (e.g. ``streamlit_sub_attractions``).
        subpath:    Subfolder inside the timestamp folder (e.g. ``location_pois``).
                    Pass ``None`` for DAGs that upload flat files directly into
                    the timestamp folder (no subfolder).
        local_dir:  Local directory to write files into.
        suffix:     File extension filter (default ``.json``).

    Returns:
        True if at least one file was downloaded, False otherwise.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        bucket = client.bucket(_BUCKET)
        # List all blobs under the dag_prefix to find timestamp folders
        all_blobs = list(bucket.list_blobs(prefix=f"{dag_prefix}/"))
        if subpath:
            target_blobs = [
                b for b in all_blobs
                if f"/{subpath}/" in b.name
                and b.name.endswith(suffix)
                and not Path(b.name).name.startswith("_")  # skip _summary.json etc.
            ]
        else:
            # Flat layout: dag_prefix/<timestamp>/<filename> — exactly 3 path parts
            target_blobs = [
                b for b in all_blobs
                if b.name.endswith(suffix)
                and not Path(b.name).name.startswith("_")
                and len(b.name.split("/")) == 3
            ]
        if not target_blobs:
            logger.debug("No blobs found under gs://%s/%s/*/%s", _BUCKET, dag_prefix, subpath or "(flat)")
            return False
        # Extract timestamps (second path component) and pick the latest
        def _timestamp(blob_name: str) -> str:
            parts = blob_name.split("/")
            return parts[1] if len(parts) > 1 else ""
        latest_ts = max(target_blobs, key=lambda b: _timestamp(b.name))
        latest_ts_str = _timestamp(latest_ts.name)
        # Download only blobs from the latest timestamp
        latest_blobs = [b for b in target_blobs if _timestamp(b.name) == latest_ts_str]
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        downloaded = 0
        for blob in latest_blobs:
            filename = Path(blob.name).name
            dest = Path(local_dir) / filename
            try:
                blob.download_to_filename(str(dest))
                downloaded += 1
            except Exception as exc:
                logger.warning("Failed to download %s: %s", blob.name, exc)
        logger.info(
            "Downloaded %d file(s) from gs://%s/%s/%s/%s → %s",
            downloaded, _BUCKET, dag_prefix, latest_ts_str, subpath or "(flat)", local_dir,
        )
        return downloaded > 0
    except Exception as exc:
        logger.warning("GCS timestamped directory download failed for %s/%s: %s", dag_prefix, subpath, exc)
        return False


# -----------------------------------------------------------------
# Named helpers — map each KG data file to its GCS location
# -----------------------------------------------------------------

def refresh_attractions(local_path: str) -> bool:
    """Try to pull the latest attractions JSON from GCS.

    Primary   (Streamlit):  streamlit_attractions/<timestamp>/touristattractionsscraper_data.json
    Fallback  (Airflow DAG): tourist_attractions_monthly/<timestamp>/tourist_attractions.json
    """
    ok = try_download_latest_in_prefix(
        "streamlit_attractions/",
        local_path,
        pattern="touristattractionsscraper_data.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "tourist_attractions_monthly/",
            local_path,
            pattern="tourist_attractions.json",
        )
    return ok


def refresh_events(local_path: str) -> bool:
    """Try to pull the latest events JSON from GCS.

    Primary   (Streamlit):   streamlit_events/<timestamp>/lankaevents_<year>.json
    Fallback  (Airflow DAG): lankaevents_monthly/<timestamp>/lankaevents_<year>.json
    """
    ok = try_download_latest_in_prefix(
        "streamlit_events/",
        local_path,
        pattern="lankaevents_",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "lankaevents_monthly/",
            local_path,
            pattern="lankaevents_",
        )
    return ok


def refresh_holidays(local_path: str) -> bool:
    """Try to pull the latest all-months holidays JSON from GCS.

    GCS path: streamlit_holidays/<timestamp>/sri_lanka_holidays_<year>_all_months.json
    Falls back to sri_lanka_holidays_annual/ if streamlit folder has no data.
    """
    ok = try_download_latest_in_prefix(
        "streamlit_holidays/",
        local_path,
        pattern="_all_months.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "sri_lanka_holidays_annual/",
            local_path,
            pattern="_all_months.json",
        )
    return ok


def refresh_hotels(local_path: str) -> bool:
    """Try to pull the latest hotels JSON from GCS.

    Primary   (Streamlit):   streamlit_hotels/<timestamp>/hotels_near_attractions.json
    Fallback  (Airflow DAG): accommodation_monthly/<timestamp>/hotels_near_attractions.json
    """
    ok = try_download_latest_in_prefix(
        "streamlit_hotels/",
        local_path,
        pattern="hotels_near_attractions.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "accommodation_monthly/",
            local_path,
            pattern="hotels_near_attractions.json",
        )
    return ok


def refresh_tourism_news(local_path: str) -> bool:
    """Try to pull tourism_news.json from GCS.

    Primary source (Airflow DAG):   tourism_news_weekly/<timestamp>/tourism_news.json
    Fallback source (Streamlit):    streamlit_news/<timestamp>/tourismnewsscraper_data.json
                                    (same content, different filename — downloaded to local_path)
    """
    ok = try_download_latest_in_prefix(
        "tourism_news_weekly/",
        local_path,
        pattern="tourism_news.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "streamlit_news/",
            local_path,
            pattern="tourismnewsscraper_data.json",
        )
    return ok


def refresh_sltda_projects(local_path: str) -> bool:
    """Try to pull sltda_projects.json from GCS.

    GCS path: sltda_projects_monthly/<timestamp>/sltda_projects.json
    Falls back to streamlit_projects/ if the monthly folder has no data.
    """
    ok = try_download_latest_in_prefix(
        "sltda_projects_monthly/",
        local_path,
        pattern="sltda_projects.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "streamlit_projects/",
            local_path,
            pattern="sltda_projects.json",
        )
    return ok


def refresh_sub_attractions(local_dir: str) -> bool:
    """Try to pull all sub-attraction JSONs from GCS into *local_dir*.

    Primary   (Streamlit):   streamlit_sub_attractions/<timestamp>/location_pois/<name>.json
    Fallback  (Airflow DAG): sub_attractions_monthly/<timestamp>/<name>.json  (flat, no subfolder)
    """
    ok = try_download_latest_timestamped_directory(
        "streamlit_sub_attractions",
        "location_pois",
        local_dir,
    )
    if not ok:
        ok = try_download_latest_timestamped_directory(
            "sub_attractions_monthly",
            None,
            local_dir,
        )
    return ok


def refresh_immigration(local_dir: str) -> bool:
    """Try to pull cleaned immigration JSONs from GCS into *local_dir*.

    Source (Airflow DAG): immigration_services_annual/<timestamp>/cleaned/*.json
    No Streamlit equivalent exists.
    """
    return try_download_latest_timestamped_directory(
        "immigration_services_annual",
        "cleaned",
        local_dir,
    )


def refresh_railway_stations(local_path: str) -> bool:
    """Try to pull railway_stations_enriched.json from GCS.

    Primary   (Streamlit):   streamlit_train_schedule/<timestamp>/stations/railway_stations_enriched.json
    Fallback  (Airflow DAG): railway_station_enrichment/<timestamp>/railway_stations_enriched.json
    """
    ok = try_download_latest_in_prefix(
        "streamlit_train_schedule/",
        local_path,
        pattern="railway_stations_enriched.json",
    )
    if not ok:
        ok = try_download_latest_in_prefix(
            "railway_station_enrichment/",
            local_path,
            pattern="railway_stations_enriched.json",
        )
    return ok

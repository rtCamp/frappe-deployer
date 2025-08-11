from frappe_manager.logger.log import richprint
from git import Object
import requests
from pathlib import Path
from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn

from typing import Union, List, Dict
import hashlib

def _get_file_hash(path, algo="sha256", chunk_size=8192):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def download_file_with_progress(
    urls: Union[str, List[dict[str,str]]],
    dest_dir: Path, 
    chunk_size: int = 8192,
    skip_if_exists: bool = True,
    check_size: bool = True,
    check_hash: bool = True,
) -> Union[Dict, List[Dict]]:
    """
    Download file(s) from URL(s) to the given destination directory, using the filename from the response,
    and showing a rich progress bar.

    Args:
        urls (str or list[str]): The URL or list of URLs to download from.
        dest_dir (Path): The destination directory.
        chunk_size (int): The chunk size for streaming download.
        skip_if_exists (bool): If True, skip download if file exists and matches size/hash.
        check_size (bool): If True, check file size before skipping.
        check_hash (bool): If True, check file hash before skipping.

    Returns:
        dict or list[dict]: Metadata for each downloaded file, including absolute path, filename, size, content_type, url.
    """
    def _download_one(url: str) -> Dict:
        # Use HEAD to get filename before downloading
        head_resp = requests.head(url, allow_redirects=True)
        content_disp = head_resp.headers.get("content-disposition")
        filename = None
        if content_disp:
            import re
            match = re.search(r'filename="?([^"]+)"?', content_disp)
            if match:
                filename = match.group(1)
        if not filename:
            from urllib.parse import urlparse
            filename = Path(urlparse(url).path).name or "downloaded_file"
        dest_path = (dest_dir / filename).absolute()

        # Caching logic
        # We will get the file size from the GET response, not HEAD, to support S3 and similar
        # So we cannot check size/hash before GET unless HEAD provides it
        # If you want to skip based on file existence only, you can do so here
        # Otherwise, do the skip check after GET

        response = requests.get(url, stream=True)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        # Try to get filename from Content-Disposition header (again, in case GET differs)
        filename = None
        content_disp = response.headers.get("content-disposition")
        if content_disp:
            import re
            match = re.search(r'filename="?([^"]+)"?', content_disp)
            if match:
                filename = match.group(1)
        if not filename:
            from urllib.parse import urlparse
            filename = Path(urlparse(url).path).name or "downloaded_file"

        dest_path = (dest_dir / filename).absolute()
        richprint.stop()

        # Caching logic after GET (now we have total size)
        if skip_if_exists and dest_path.exists():
            size_matches = not check_size or dest_path.stat().st_size == total
            hash_matches = True

            if check_hash and total > 0:
                expected_hash = None
                # Try to get hash from standard or custom headers
                for hash_header in ["X-Checksum-Sha256", "X-Checksum-Sha1", "X-Checksum-Md5", "Content-MD5"]:
                    if hash_header in response.headers:
                        expected_hash = response.headers[hash_header]
                        break

                if expected_hash:
                    if hash_header == "Content-MD5":
                        import base64
                        actual_md5 = _get_file_hash(dest_path, "md5")
                        actual_md5_b64 = base64.b64encode(bytes.fromhex(actual_md5)).decode()
                        hash_matches = (actual_md5_b64 == expected_hash)
                    else:
                        actual_hash = _get_file_hash(dest_path)
                        hash_matches = (actual_hash.lower() == expected_hash.lower())
                else:
                    hash_matches = True

            if size_matches and hash_matches:
                return {
                    "absolute_path": str(dest_path),
                    "filename": filename,
                    "size": dest_path.stat().st_size,
                    "content_type": response.headers.get("content-type"),
                    "url": url,
                    "skipped": True,
                }

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(f"Downloading {filename}", total=total if total > 0 else None)
            with open(dest_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        progress.update(task, advance=len(chunk))

        richprint.start("Working")

        return {
            "absolute_path": str(dest_path),
            "filename": filename,
            "size": dest_path.stat().st_size,
            "content_type": response.headers.get("content-type"),
            "url": url,
            "skipped": False,
        }

    if isinstance(urls, str):
        return _download_one(urls)
    else:
        for key, value in urls.items():
            urls[key] = _download_one(value)
        return urls

import requests
from pathlib import Path
from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn

def download_file_with_progress(url: str, dest_path: Path, chunk_size: int = 8192):
    """
    Download a file from a URL to the given destination path, showing a rich progress bar.

    Args:
        url (str): The URL to download from.
        dest_path (Path): The destination file path.
        chunk_size (int): The chunk size for streaming download.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {dest_path.name}", total=total)
        with open(dest_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file.write(chunk)
                    progress.update(task, advance=len(chunk))

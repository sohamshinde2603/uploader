import os
import re
import time
import mmap
import datetime
import aiohttp
import aiofiles
import asyncio
import logging

# Retry counter used by download_video()
failed_counter = 0
import requests
import tgcrypto
import subprocess
import concurrent.futures
from math import ceil
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from urllib.parse import urlparse

def duration(filename):
    if not Path(filename).exists():
        print(f"❌ File not found for duration: {filename}")
        return 0.0

    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", filename
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        output = result.stdout.decode().strip()
        return float(output)
    except Exception as e:
        print(f"❌ Failed to get duration for {filename}: {e}")
        return 0.0

def get_mps_and_keys(api_url):
    response = requests.get(api_url)
    response_json = response.json()
    mpd = response_json.get('MPD')
    keys = response_json.get('KEYS')
    return mpd, keys
   
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka

async def pdf_download(url, file_name, chunk_size=1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name   
   

def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


import os
import subprocess
from pathlib import Path

async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Step 1: Download with yt-dlp
        cmd1 = f'yt-dlp -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-formats --no-check-certificate --external-downloader aria2c "{mpd_url}"'
        print(f"▶️ Downloading: {cmd1}")
        subprocess.run(cmd1, shell=True)

        # Step 2: Detect downloaded files
        video_file = None
        audio_file = None
        for f in output_path.iterdir():
            if f.suffix in [".mp4", ".webm"] and not video_file:
                video_file = f
            elif f.suffix in [".m4a", ".webm"] and not audio_file:
                audio_file = f

        if not video_file or not audio_file:
            raise FileNotFoundError("❌ Decryption failed: video or audio file not found.")

        # Step 3: Decrypt
        decrypted_video = output_path / "video.mp4"
        decrypted_audio = output_path / "audio.m4a"

        subprocess.run(f'mp4decrypt {keys_string} "{video_file}" "{decrypted_video}"', shell=True)
        subprocess.run(f'mp4decrypt {keys_string} "{audio_file}" "{decrypted_audio}"', shell=True)

        video_file.unlink(missing_ok=True)
        audio_file.unlink(missing_ok=True)

        # Step 4: Merge
        final_file = output_path / f"{output_name}.mp4"
        subprocess.run(f'ffmpeg -y -i "{decrypted_video}" -i "{decrypted_audio}" -c copy "{final_file}"', shell=True)

        decrypted_video.unlink(missing_ok=True)
        decrypted_audio.unlink(missing_ok=True)

        if not final_file.exists():
            raise FileNotFoundError("❌ Merged video file not found.")

        print(f"✅ Final video ready: {final_file}")
        return str(final_file)

    except Exception as e:
        print(f"🔥 Error in decrypt_and_merge_video: {e}")
        return None

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name

# appx zip ke liye 
# helper.py
import os
import requests
import zipfile
import subprocess
import tempfile
import shutil

FIXED_REFERER = "https://player.akamai.net.in/"

def process_zip_to_video(url, name):
    temp_dir = tempfile.mkdtemp(prefix="zip_")

    zip_path = os.path.join(temp_dir, "file.zip")
    extract_dir = os.path.join(temp_dir, "extract")
    output_path = os.path.join(temp_dir, f"{name}.mp4")

    headers = {
        "User-Agent": "Mozilla/5.0 (Android)",
        "Referer": FIXED_REFERER,
        "Range": "bytes=0-"
    }

    # 1️⃣ ZIP DOWNLOAD (FIXED REFERER)
    with requests.get(url, headers=headers, stream=True, timeout=20) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    # 2️⃣ EXTRACT ZIP
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    # 3️⃣ FIND m3u8
    m3u8_path = None
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.endswith(".m3u8"):
                m3u8_path = os.path.join(root, f)
                break

    if not m3u8_path:
        shutil.rmtree(temp_dir)
        raise Exception("❌ m3u8 file nahi mili")

    # 4️⃣ m3u8 → MP4 (same referer ffmpeg me bhi)
    cmd = [
        "ffmpeg",
        "-y",
        "-headers", f"Referer: {FIXED_REFERER}\r\n",
        "-allowed_extensions", "ALL",
        "-i", m3u8_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd)

    return output_path, temp_dir

import os, requests, zipfile, subprocess

import zipfile

def extract_zip(zip_path: str) -> str:
    extract_dir = zip_path.replace(".zip", "")
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    return extract_dir


import subprocess

def merge_ts_files(folder: str, output: str):
    ts_files = sorted(
        f for f in os.listdir(folder)
        if f.endswith((".ts", ".tse"))
    )

    list_file = os.path.join(folder, "list.txt")
    with open(list_file, "w") as f:
        for ts in ts_files:
            f.write(f"file '{os.path.join(folder, ts)}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output
    ], check=True)

    return output


def download_drago_mkv(url: str, filename: str, ext: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://akstechnicalclasses.classx.co.in/",
        "Origin": "https://akstechnicalclasses.classx.co.in",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{filename}.{ext}"

    session = create_session()
    downloaded = 0

    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)
        headers["Range"] = f"bytes={downloaded}-"

    try:
        with session.get(url, headers=headers, stream=True, timeout=(10, 180)) as r:
            if r.status_code not in (200, 206):
                print(f"❌ Bad status: {r.status_code}")
                return None

            total = int(r.headers.get("content-length", 0)) + downloaded
            chunk_size = 256 * 1024

            with open(file_path, "ab") as f, tqdm(
                total=total,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=filename,
                ncols=80
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        return file_path

    except Exception as e:
        print(f"⚠️ Download interrupted (resume enabled): {e}")
        return file_path if os.path.exists(file_path) else None

def download_drago_mkv(url: str, name: str, ext: str = None) -> str | None:
    """Download signed AppX video ZIPs and turn their TS segments into MP4."""
    try:
        parsed = urlparse(url)
        path_ext = os.path.splitext(parsed.path)[1].lower()
        actual_ext = (ext or path_ext.lstrip(".") or "mkv").lower()

        os.makedirs("downloads", exist_ok=True)

        # Signed static-trans URLs are ZIP archives. Download them directly
        # to a real .zip file; do not use the legacy .mkv raw downloader.
        if actual_ext == "zip" or path_ext == ".zip":
            zip_path = os.path.join("downloads", f"{name}.zip")
            extract_dir = os.path.join("downloads", f"{name}_extract")
            output_path = os.path.join("downloads", f"{name}.mp4")

            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
                "Referer": "https://akstechnicalclasses.classx.co.in/",
                "Origin": "https://akstechnicalclasses.classx.co.in",
                "Accept": "*/*",
                "Connection": "keep-alive",
            }

            print(f"📦 Downloading signed ZIP: {url}")

            # Always start clean. A previous partial ZIP must never be
            # appended to a new signed URL.
            for old in (zip_path, output_path):
                try:
                    if os.path.isfile(old):
                        os.remove(old)
                except OSError:
                    pass

            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=(20, 300),
                allow_redirects=True,
            )
            print(f"📦 ZIP HTTP status: {response.status_code}")
            response.raise_for_status()

            total = 0
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)

            response.close()

            print(f"📦 ZIP downloaded: {total} bytes")

            if total == 0 or not os.path.isfile(zip_path):
                print("❌ Signed ZIP response was empty.")
                return None

            # A ZIP starts with PK. ZipFile gives a stronger validation.
            if not zipfile.is_zipfile(zip_path):
                with open(zip_path, "rb") as f:
                    prefix = f.read(64)
                print(
                    "❌ Response is not a valid ZIP. "
                    f"Content-Type={response.headers.get('Content-Type')}; "
                    f"starts={prefix!r}"
                )
                return None

            # Remove an old extraction directory.
            if os.path.isdir(extract_dir):
                shutil.rmtree(extract_dir)

            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            # Find TS/TSE files recursively. Some AppX archives contain
            # subdirectories rather than placing the segments at the root.
            ts_files = []
            for root, _, files in os.walk(extract_dir):
                for filename in files:
                    if filename.lower().endswith((".ts", ".tse")):
                        ts_files.append(os.path.join(root, filename))

            if not ts_files:
                print("❌ ZIP contains no .ts/.tse video segments.")
                return None

            # Sort naturally by numeric parts where possible.
            def segment_key(path):
                base = os.path.basename(path)
                parts = re.split(r"(\d+)", base)
                return [
                    int(x) if x.isdigit() else x.lower()
                    for x in parts
                ]

            ts_files.sort(key=segment_key)

            list_file = os.path.join(extract_dir, "list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for segment in ts_files:
                    # concat demuxer requires escaped single quotes.
                    safe = os.path.abspath(segment).replace("'", r"'\''")
                    f.write(f"file '{safe}'\n")

            print(f"🎬 Merging {len(ts_files)} video segments...")

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_file,
                    "-c",
                    "copy",
                    output_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

            if (
                os.path.isfile(output_path)
                and os.path.getsize(output_path) > 0
            ):
                print(
                    f"✅ Final MP4: {output_path} "
                    f"({os.path.getsize(output_path)} bytes)"
                )
                return output_path

            print("❌ FFmpeg did not create a valid MP4.")
            return None

        # Non-ZIP fallback.
        return download_raw_file(url, name)

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg merge failed: {e.stderr[-4000:] if e.stderr else e}")
        return None
    except Exception as e:
        print(f"❌ Signed video download failed: {type(e).__name__}: {e}")
        logging.exception("Signed video download failed")
        return None

def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"

import os, re, asyncio, aiohttp
from urllib.parse import urljoin, urlparse

async def fetch_segment(session, seg_url, headers):
    async with session.get(seg_url, headers=headers, timeout=30) as resp:
        resp.raise_for_status()
        return await resp.read()

import aiohttp
import asyncio
import os
from urllib.parse import urljoin, urlparse

async def fetch_segment(session, seg_url, f):
    async with session.get(seg_url) as resp:
        resp.raise_for_status()
        while True:
            chunk = await resp.content.read(1024*1024)
            if not chunk:
                break
            f.write(chunk)

async def download_m3u8_async(url: str, filename: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://player.akamai.net.in/",
        "Origin": "https://player.akamai.net.in",
        "Accept": "*/*"
    }
    os.makedirs("downloads", exist_ok=True)
    final_file = f"downloads/{filename}.mp4"

    async with aiohttp.ClientSession(headers=headers) as session:
        r = await session.get(url)
        text = await r.text()
        playlist_lines = text.splitlines()
        segments = [urljoin(url, line) for line in playlist_lines if line and not line.startswith("#")]

        if not segments:
            print("❌ No segments found!")
            return None

        print(f"🚀 Downloading {len(segments)} segments for {filename}...")

        # HLS segments MUST be written in playlist order.
        # Concurrent writes to the same file can scramble the video.
        with open(final_file, "wb") as f:
            for index, seg_url in enumerate(segments, 1):
                print(f"📥 Downloading segment {index}/{len(segments)}")
                await fetch_segment(session, seg_url, f)

        print(f"\n✅ Full video downloaded: {final_file}")
        return final_file

# Run
# asyncio.run(download_m3u8_async("your_m3u8_url", "video_name"))
import os
import asyncio
import subprocess
import logging

async def download_video(url, cmd, name):
    """Run the existing video downloader and return only a real file path.

    This wrapper does not alter or bypass any DRM/license mechanism.
    It only validates downloader output and reports useful failures.
    """
    global failed_counter

    try:
        print(f"🎬 Starting video download: {name}")
        print(f"🔗 URL type: {urlparse(url).path.rsplit('/', 1)[-1]}")

        # Preserve the existing ZIP/M3U8/yt-dlp routing.
        url_path = urlparse(url).path.lower()

        if url_path.endswith(".zip") and "static-trans" in url_path:
            print("📦 Signed ZIP video detected.")
            result = download_drago_mkv(url, name, "zip")

        elif "transcoded" in url.lower():
            print("⚡ Transcoded/HLS URL detected.")
            result = await download_m3u8_async(url, name)

        else:
            download_cmd = re.sub(
                r'\s+--external-downloader(?:=|\s+)aria2c',
                '',
                cmd,
                flags=re.IGNORECASE,
            )
            download_cmd = re.sub(
                r'\s+--downloader-args(?:=|\s+)"aria2c:[^"]*"',
                '',
                download_cmd,
                flags=re.IGNORECASE,
            )
            download_cmd = re.sub(
                r"\s+--downloader-args(?:=|\s+)'aria2c:[^']*'",
                '',
                download_cmd,
                flags=re.IGNORECASE,
            )

            download_cmd = (
                f'{download_cmd} '
                f'--retries 25 '
                f'--fragment-retries 25 '
                f'--file-access-retries 25 '
                f'--no-mtime '
                f'--no-part '
                f'--print after_move:filepath'
            )

            print("[VIDEO DOWNLOAD COMMAND]")
            print(download_cmd)

            process = await asyncio.create_subprocess_shell(
                download_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            stdout_text = stdout.decode(errors="ignore")
            stderr_text = stderr.decode(errors="ignore")

            print("[YT-DLP STDOUT]")
            print(stdout_text)
            if stderr_text:
                print("[YT-DLP STDERR]")
                print(stderr_text)

            if process.returncode != 0:
                failed_counter = 0
                return None

            candidates = []

            for line in reversed(
                (stdout_text + "\n" + stderr_text).splitlines()
            ):
                candidate = line.strip().strip('"').strip("'")
                if (
                    candidate
                    and os.path.isfile(candidate)
                    and os.path.getsize(candidate) > 0
                ):
                    candidates.append(candidate)

            base = os.path.splitext(name)[0]
            candidates.extend([
                name,
                f"{name}.webm",
                f"{name}.mp4",
                f"{name}.mkv",
                f"{name}.mp4.webm",
                f"{base}.mp4",
                f"{base}.mkv",
                f"{base}.webm",
                f"{base}.mp4.webm",
            ])

            for root in (".", "downloads"):
                if os.path.isdir(root):
                    for dirpath, _, filenames in os.walk(root):
                        for filename in filenames:
                            if filename.lower().endswith(
                                (".mp4", ".mkv", ".webm", ".mov", ".m4v")
                            ):
                                candidates.append(
                                    os.path.join(dirpath, filename)
                                )

            result = None
            seen = set()

            for candidate in candidates:
                if not isinstance(candidate, (str, bytes, os.PathLike)):
                    continue

                candidate = os.path.normpath(candidate)
                if candidate in seen:
                    continue
                seen.add(candidate)

                if (
                    os.path.isfile(candidate)
                    and os.path.getsize(candidate) > 0
                ):
                    result = candidate
                    break

        # CRITICAL: validate before returning. os.path.isfile() requires
        # a real path-like value; never pass None downstream.
        if not isinstance(result, (str, bytes, os.PathLike)):
            print(
                "❌ Downloader returned no path. "
                "The underlying download/decryption step failed."
            )
            return None

        if not os.path.isfile(result):
            print(f"❌ Downloader returned missing file: {result!r}")
            return None

        if os.path.getsize(result) <= 0:
            print(f"❌ Downloader returned an empty file: {result!r}")
            return None

        failed_counter = 0
        print(
            f"✅ Valid video file: {result} "
            f"({os.path.getsize(result)} bytes)"
        )
        return result

    except Exception as e:
        print(f"❌ Video download exception: {type(e).__name__}: {e}")
        logging.exception("Video download exception")
        return None

def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=10,
        pool_maxsize=10
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
import os
import mmap
import requests
from tqdm import tqdm
from base64 import b64decode

# ==============================
# FILE DECRYPT FUNCTION
# ==============================
def decrypt_file(file_path: str, key: str) -> bool:
    if not file_path or not os.path.exists(file_path):
        return False

    if not key:
        return True

    key_bytes = key.encode()
    size = min(28, os.path.getsize(file_path))

    with open(file_path, "r+b") as f:
        with mmap.mmap(f.fileno(), length=size, access=mmap.ACCESS_WRITE) as mm:
            for i in range(size):
                mm[i] ^= key_bytes[i] if i < len(key_bytes) else i

    return True
# ==============================
# RAW FILE DOWNLOAD
# ==============================
def download_raw_file(url: str, filename: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://akstechnicalclasses.classx.co.in/",
        "Origin": "https://akstechnicalclasses.classx.co.in",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{filename}.mkv"

    session = create_session()
    downloaded = 0

    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)
        headers["Range"] = f"bytes={downloaded}-"

    try:
        with session.get(url, headers=headers, stream=True, timeout=(10, 180)) as r:
            if r.status_code not in (200, 206):
                print(f"❌ Bad status: {r.status_code}")
                return None

            total = int(r.headers.get("content-length", 0)) + downloaded
            chunk_size = 256 * 1024

            with open(file_path, "ab") as f, tqdm(
                total=total,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=filename,
                ncols=80
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
            return file_path

        print("❌ Download completed but output file is empty.")
        return None

    except Exception as e:
        print(f"⚠️ Download interrupted (resume enabled): {e}")
        if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        return None
# ==============================
# DOWNLOAD + DECRYPT WRAPPER
# ==============================

def download_and_decrypt_video(url: str, name: str, key: str = None) -> str | None:
    video_path = None

    for _ in range(5):  # resume attempts
        video_path = download_raw_file(url, name)
        if video_path and os.path.getsize(video_path) > 10 * 1024 * 1024:
            break

    if not video_path:
        return None

    if decrypt_file(video_path, key):
        return video_path

    return None

# ==============================
# EXAMPLE USAGE
# ==============================


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name, channel_id):
    reply = await bot.send_message(channel_id, f"Downloading pdf:\n<pre><code>{name}</code></pre>")
    time.sleep(1)
    start_time = time.time()
    await bot.send_document(ka, caption=cc1)
    count+=1
    await reply.delete (True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3) 



import asyncio

import asyncio

import asyncio

import os




    
import os
import time
import asyncio

# 🔹 Async ffmpeg runner (NO BLOCKING)
async def run_cmd(cmd: str):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()


async def send_vid(
    bot: Client,
    m: Message,
    cc,
    filename,
    vidwatermark,
    thumb,
    name,
    prog,
    channel_id
):
    # ==========================
    # INPUT FILE SAFETY CHECK
    # ==========================
    if not isinstance(filename, (str, bytes, os.PathLike)):
        await m.reply_text(
            "❌ Video download failed. No valid output file was created."
        )
        return

    if not os.path.isfile(filename):
        await m.reply_text(
            f"❌ Video file not found: `{filename}`"
        )
        return

    if os.path.getsize(filename) <= 0:
        await m.reply_text(
            "❌ Video file is empty."
        )
        return

    # ==========================
    # THUMBNAIL GENERATION
    # ==========================
    thumb_path = f"{filename}.jpg"
    await run_cmd(
        f'ffmpeg -y -i "{filename}" -ss 00:00:10 -vframes 1 "{thumb_path}"'
    )

    await prog.delete(True)

    reply1 = await bot.send_message(
        channel_id,
        f"**📩 Uploading Video 📩:-**\n<blockquote>**{name}**</blockquote>"
    )

    reply = await m.reply_text(
        f"**Generate Thumbnail:**\n<blockquote>**{name}**</blockquote>"
    )

    # ==========================
    # THUMB SELECTION
    # ==========================
    thumbnail = thumb_path if thumb == "/d" else thumb

    # ==========================
    # WATERMARK PROCESS
    # ==========================
    if vidwatermark == "/d":
        w_filename = filename
    else:
        w_filename = f"w_{os.path.basename(filename)}"
        font_path = "vidwater.ttf"

        await run_cmd(
            f'ffmpeg -y -i "{filename}" -vf '
            f'"drawtext=fontfile={font_path}:text=\'{vidwatermark}\':'
            f'fontcolor=white@0.3:fontsize=h/6:'
            f'x=(w-text_w)/2:y=(h-text_h)/2" '
            f'-codec:a copy "{w_filename}"'
        )

    # ==========================
    # SAFETY CHECK
    # ==========================
    if not os.path.exists(w_filename):
        await m.reply_text("❌ Video processing failed")
        return

    dur = int(duration(w_filename))
    start_time = time.time()

    # ==========================
    # UPLOAD (VIDEO → DOC FALLBACK)
    # ==========================
    try:
        await bot.send_video(
            chat_id=channel_id,
            video=w_filename,
            caption=cc,
            supports_streaming=True,
            height=720,
            width=1280,
            thumb=thumbnail,
            duration=dur,
            progress=progress_bar,
            progress_args=(reply, start_time)
        )
    except Exception:
        await bot.send_document(
            chat_id=channel_id,
            document=w_filename,
            caption=cc,
            progress=progress_bar,
            progress_args=(reply, start_time)
        )

    # ==========================
    # CLEANUP
    # ==========================
    
    except Exception:
        await bot.send_document(channel_id, w_filename, caption=cc, progress=progress_bar, progress_args=(reply, start_time))
    os.remove(w_filename)
    await reply.delete(True)
    await reply1.delete(True)
    os.remove(f"{filename}.jpg")

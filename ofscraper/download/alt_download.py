r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
import pathlib
import re
import subprocess
import traceback
from functools import partial

import aiofiles
import arrow
import psutil
from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_message,
    stop_after_attempt,
    wait_random,
)

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.common.common as common
import ofscraper.download.common.globals as common_globals
import ofscraper.download.common.keyhelpers as keyhelpers
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.settings as settings
from ofscraper.download.common.common import (
    addGlobalDir,
    check_forced_skip,
    downloadspace,
    get_item_total,
    get_medialog,
    get_resume_size,
    get_url_log,
    moveHelper,
    path_to_file_logger,
    set_time,
    size_checker,
    temp_file_logger,
)


async def alt_download(c, ele, username, model_id, job_progress):
    common_globals.log.debug(
        f"{get_medialog(ele)} Downloading with protected media downloader"
    )
    sharedPlaceholderObj = await placeholder.Placeholders(ele, "mp4").init()
    common_globals.log.debug(f"{get_medialog(ele)} download url:  {get_url_log(ele)}")

    audio, video = await ele.mpd_dict
    path_to_file_logger(sharedPlaceholderObj, ele)

    audio = await alt_download_downloader(audio, c, ele, job_progress)
    video = await alt_download_downloader(video, c, ele, job_progress)

    post_result = await media_item_post_process(audio, video, ele, username, model_id)
    if post_result:
        return post_result
    await media_item_keys(c, audio, video, ele)

    return await handle_result(
        sharedPlaceholderObj, ele, audio, video, username, model_id
    )


async def handle_result(sharedPlaceholderObj, ele, audio, video, username, model_id):
    tempPlaceholder = await placeholder.tempFilePlaceholder(
        ele, f"temp_{ele.id or await ele.final_filename}.mp4"
    ).init()
    temp_path = tempPlaceholder.tempfilepath
    temp_path.unlink(missing_ok=True)
    t = subprocess.run(
        [
            settings.get_ffmpeg(),
            "-i",
            str(video["path"]),
            "-i",
            str(audio["path"]),
            "-c",
            "copy",
            "-movflags",
            "use_metadata_tags",
            str(temp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if t.stderr.decode().find("Output") == -1:
        common_globals.log.debug(f"{get_medialog(ele)} ffmpeg failed")
        common_globals.log.debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        common_globals.log.debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)

    common_globals.log.debug(
        f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filepath}"
    )
    moveHelper(temp_path, sharedPlaceholderObj.trunicated_filepath, ele)
    addGlobalDir(sharedPlaceholderObj.trunicated_filepath)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common_globals.log.debug(
            f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        set_time(sharedPlaceholderObj.trunicated_filepath, newDate)
        common_globals.log.debug(
            f"{get_medialog(ele)} Date set to {arrow.get(sharedPlaceholderObj.trunicated_filepath.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await operations.download_media_update(
            ele,
            filename=sharedPlaceholderObj.trunicated_filepath,
            model_id=model_id,
            username=username,
            downloaded=True,
            hashdata=await common.get_hash(
                sharedPlaceholderObj, mediatype=ele.mediatype
            ),
        )
    return ele.mediatype, video["total"] + audio["total"]


async def media_item_post_process(audio, video, ele, username, model_id):
    if (audio["total"] + video["total"]) == 0:
        if ele.mediatype != "forced_skipped":
            await operations.download_media_update(
                ele,
                filename=None,
                model_id=model_id,
                username=username,
                downloaded=True,
            )
        return ele.mediatype, 0
    for m in [audio, video]:
        m["total"] = get_item_total(m)

    for m in [audio, video]:
        if not isinstance(m, dict):
            return m
        await size_checker(m["path"], ele, m["total"])


async def media_item_keys(c, audio, video, ele):
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele)


async def alt_download_downloader(item, c, ele, job_progress):
    downloadspace(mediatype=ele.mediatype)
    placeholderObj = await placeholder.tempFilePlaceholder(
        ele, f"{item['name']}.part"
    ).init()
    item["path"] = placeholderObj.tempfilepath
    item["total"] = None
    async for _ in AsyncRetrying(
        stop=stop_after_attempt(constants.getattr("DOWNLOAD_FILE_RETRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN_WAIT_API"),
            max=constants.getattr("OF_MAX_WAIT_API"),
        ),
        retry=retry_if_not_exception_message(
            constants.getattr("SPACE_DOWNLOAD_MESSAGE")
        ),
        reraise=True,
    ):
        with _:
            try:
                _attempt = common.alt_attempt_get(item)
                _attempt.set(_attempt.get(0) + 1)
                (
                    pathlib.Path(placeholderObj.tempfilepath).unlink(missing_ok=True)
                    if _attempt.get() > 1
                    else None
                )
                data = await asyncio.get_event_loop().run_in_executor(
                    common_globals.cache_thread,
                    partial(cache.get, f"{item['name']}_headers"),
                )
                if data:
                    return await main_data_handler(
                        data, item, c, ele, placeholderObj, job_progress
                    )

                else:
                    return await alt_data_handler(
                        item, c, ele, placeholderObj, job_progress
                    )
            except OSError as E:
                await asyncio.sleep(1)
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Number of Open Files -> { len(psutil.Process().open_files())}"
                )
                common_globals.log.debug(
                    f" {get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                )
                raise E
            except Exception as E:
                await asyncio.sleep(1)
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] {traceback.format_exc()}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] {E}"
                )
                raise E


async def main_data_handler(data, item, c, ele, placeholderObj, job_progress):
    item["total"] = int(data.get("content-length"))
    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    if await check_forced_skip(ele, item["total"]):
        item["total"] = 0
        return item
    elif item["total"] == resume_size:
        temp_file_logger(placeholderObj, ele)
        return item
    elif item["total"] != resume_size:
        return await alt_download_sendreq(item, c, ele, placeholderObj, job_progress)


async def alt_data_handler(item, c, ele, placeholderObj, job_progress):
    result = None
    try:
        result = await alt_download_sendreq(item, c, ele, placeholderObj, job_progress)
    except Exception as E:
        raise E
    return result


async def alt_download_sendreq(item, c, ele, placeholderObj, job_progress):
    try:
        _attempt = common.alt_attempt_get(item)
        item["total"] = item["total"] if _attempt == 1 else None
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"
        common_globals.log.debug(
            f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] download temp path {placeholderObj.tempfilepath}"
        )
        return await send_req_inner(c, ele, item, placeholderObj, job_progress)
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, item, placeholderObj, job_progress):
    old_total = item["total"]
    total = old_total
    try:
        await common.total_change_helper(None, total)
        resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
        headers = (
            None
            if resume_size == 0 or not total
            else {"Range": f"bytes={resume_size}-{total}"}
        )
        params = {
            "Policy": ele.policy,
            "Key-Pair-Id": ele.keypair,
            "Signature": ele.signature,
        }
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"

        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common.alt_attempt_get(item).get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Downloading media with url {url}"
        )
        async with c.requests_async(url=url, headers=headers, params=params) as l:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread,
                partial(
                    cache.set,
                    f"{item['name']}_headers",
                    {
                        "content-length": l.headers.get("content-length"),
                        "content-type": l.headers.get("content-type"),
                    },
                ),
            )
            new_total = int(l.headers["content-length"])
            temp_file_logger(placeholderObj, ele)
            if await check_forced_skip(ele, new_total):
                item["total"] = 0
                await common.total_change_helper(None, old_total)
            elif total != resume_size:
                item["total"] = new_total
                total = new_total
                await common.total_change_helper(old_total, total)
                await download_fileobject_writer(
                    total, l, ele, job_progress, placeholderObj
                )
        await size_checker(placeholderObj.tempfilepath, ele, total)
        return item
    except Exception as E:
        await common.total_change_helper(None, -(total or 0))
        raise E


async def download_fileobject_writer(total, l, ele, job_progress, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)

    downloadprogress = settings.get_download_bars()

    task1 = job_progress.add_task(
        f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
        total=total,
        visible=True if downloadprogress else False,
    )
    count = 0
    loop = asyncio.get_event_loop()

    fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
    download_sleep = constants.getattr("DOWNLOAD_SLEEP")
    try:
        async for chunk in l.iter_chunked(constants.getattr("maxChunkSize")):
            if downloadprogress:
                count = count + 1
            common_globals.log.trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(placeholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            await fileobject.write(chunk)
            if (count + 1) % constants.getattr("CHUNK_ITER") == 0:
                await loop.run_in_executor(
                    common_globals.thread,
                    partial(
                        job_progress.update,
                        task1,
                        completed=pathlib.Path(placeholderObj.tempfilepath)
                        .absolute()
                        .stat()
                        .st_size,
                    ),
                )
            (await asyncio.sleep(download_sleep)) if download_sleep else None
    except Exception as E:
        raise E
    finally:
        # Close file if needed
        try:
            await fileobject.close()
        except Exception:
            None

        try:
            job_progress.remove_task(task1)
        except Exception:
            None

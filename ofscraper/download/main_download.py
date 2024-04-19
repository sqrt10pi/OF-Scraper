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
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.settings as settings
from ofscraper.download.common.common import (
    addGlobalDir,
    check_forced_skip,
    downloadspace,
    get_data,
    get_medialog,
    get_resume_size,
    get_unknown_content_type,
    get_url_log,
    moveHelper,
    path_to_file_logger,
    set_profile_cache_helper,
    set_time,
    size_checker,
)


async def main_download(c, ele, username, model_id, job_progress):
    common_globals.log.debug(f"{get_medialog(ele)} Downloading with normal downloader")
    common_globals.log.debug(f"{get_medialog(ele)} download url:  {get_url_log(ele)}")
    # total may be none if no .part file
    result = await main_download_downloader(
        c,
        ele,
        job_progress,
    )

    # special case for zero byte files
    if result[0] == 0:
        if ele.mediatype != "forced_skipped":
            await operations.download_media_update(
                ele,
                filename=None,
                model_id=model_id,
                username=username,
                downloaded=True,
            )
        return ele.mediatype, 0
    return await handle_result(result, ele, username, model_id)


async def handle_result(result, ele, username, model_id):
    total, temp, placeholderObj = result
    path_to_file = placeholderObj.trunicated_filepath
    await size_checker(temp, ele, total)
    common_globals.log.debug(
        f"{get_medialog(ele)} {await ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}"
    )
    common_globals.log.debug(
        f"{get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}"
    )
    moveHelper(temp, path_to_file, ele)
    addGlobalDir(placeholderObj.filedir)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common_globals.log.debug(
            f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        set_time(path_to_file, newDate)
        common_globals.log.debug(
            f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )

    if ele.id:
        await operations.download_media_update(
            ele,
            filename=path_to_file,
            model_id=model_id,
            username=username,
            downloaded=True,
            hashdata=await common.get_hash(path_to_file, mediatype=ele.mediatype),
        )
    await set_profile_cache_helper(ele)
    return ele.mediatype, total


async def main_download_downloader(c, ele, job_progress):
    downloadspace(mediatype=ele.mediatype)
    tempholderObj = await placeholder.tempFilePlaceholder(
        ele, f"{await ele.final_filename}_{ele.id}.part"
    ).init()
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
                data = await get_data(ele)
                common_globals.attempt.set(common_globals.attempt.get(0) + 1)
                (
                    pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                    if common_globals.attempt.get() > 1
                    else None
                )
                if data:
                    return await main_data_handler(
                        data, c, tempholderObj, ele, job_progress
                    )
                else:
                    return await alt_data_handler(c, tempholderObj, ele, job_progress)
            except OSError as E:
                await asyncio.sleep(1)
                common_globals.log.debug(
                    f"[attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Number of Open Files -> { len(psutil.Process().open_files())}"
                )
                common_globals.log.debug(
                    f"[attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Open Files  -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                )
                raise E
            except Exception as E:
                await asyncio.sleep(1)
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] {traceback.format_exc()}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] {E}"
                )
                raise E


async def alt_data_handler(c, tempholderObj, ele, job_progress):
    result = None
    try:
        result = await main_download_sendreq(
            c, ele, tempholderObj, job_progress, placeholderObj=None, total=None
        )
    except Exception as E:
        raise E
    return result


async def main_data_handler(data, c, tempholderObj, ele, job_progress):
    content_type = data.get("content-type").split("/")[-1]
    total = int(data.get("content-length"))
    placeholderObj = await placeholder.Placeholders(ele, content_type).init()
    resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
    # other
    if await check_forced_skip(ele, total) == 0:
        path_to_file_logger(placeholderObj, ele)
        return [0]
    elif total == resume_size:
        path_to_file_logger(placeholderObj, ele)
        return (
            total,
            tempholderObj.tempfilepath,
            placeholderObj,
        )

    else:
        try:
            return await main_download_sendreq(
                c,
                ele,
                tempholderObj,
                job_progress,
                total=total,
                placeholderObj=placeholderObj,
            )
        except Exception as E:
            raise E


async def main_download_sendreq(
    c, ele, tempholderObj, job_progress, total=None, placeholderObj=None
):
    try:
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] download temp path {tempholderObj.tempfilepath}"
        )
        total = total if common_globals.attempt.get() == 1 else None
        return await send_req_inner(
            c,
            ele,
            tempholderObj,
            job_progress,
            placeholderObj=placeholderObj,
            total=total,
        )
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(
    c, ele, tempholderObj, job_progress, placeholderObj=None, total=None
):
    old_total = total
    try:
        await common.total_change_helper(None, total)
        resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
        headers = (
            None
            if resume_size == 0 or not total
            else {"Range": f"bytes={resume_size}-{total}"}
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_RETRIES')}] Downloading media with url {ele.url}"
        )
        async with c.requests_async(url=ele.url, headers=headers) as r:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread,
                partial(
                    cache.set,
                    f"{ele.id}_headers",
                    {
                        "content-length": r.headers.get("content-length"),
                        "content-type": r.headers.get("content-type"),
                    },
                ),
            )
            new_total = int(r.headers["content-length"])
            content_type = r.headers.get("content-type").split("/")[-1]
            content_type = content_type or get_unknown_content_type(ele)
            if not placeholderObj:
                placeholderObj = await placeholder.Placeholders(
                    ele, content_type
                ).init()
            path_to_file_logger(placeholderObj, ele)
            if await check_forced_skip(ele, new_total):
                total = 0
                await common.total_change_helper(old_total, total)
            elif total != resume_size:
                total = new_total
                await common.total_change_helper(old_total, total)
                await download_fileobject_writer(
                    r, job_progress, ele, tempholderObj, placeholderObj, total
                )

        await size_checker(tempholderObj.tempfilepath, ele, total)
        return (total, tempholderObj.tempfilepath, placeholderObj)
    except Exception as E:
        await common.total_change_helper(None, -(total or 0))
        raise E


async def download_fileobject_writer(
    r, job_progress, ele, tempholderObj, placeholderObj, total
):
    pathstr = str(placeholderObj.trunicated_filepath)
    downloadprogress = settings.get_download_bars()
    task1 = job_progress.add_task(
        f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
        total=total,
        visible=True if downloadprogress else False,
    )
    try:
        count = 0
        loop = asyncio.get_event_loop()
        fileobject = await aiofiles.open(tempholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")

        async for chunk in r.iter_chunked(constants.getattr("maxChunkSize")):
            if downloadprogress:
                count = count + 1
            await fileobject.write(chunk)
            common_globals.log.trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            if (count + 1) % constants.getattr("CHUNK_ITER") == 0:
                await loop.run_in_executor(
                    common_globals.thread,
                    partial(
                        job_progress.update,
                        task1,
                        completed=pathlib.Path(tempholderObj.tempfilepath)
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

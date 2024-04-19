import asyncio
import json
import pathlib
import re
import subprocess
import traceback
from functools import partial

from bs4 import BeautifulSoup
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.download.common.globals as common_globals
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.download.common.common import get_medialog

log = None


def setLog(input_):
    global log
    log = input_


async def un_encrypt(item, c, ele, input_=None):
    setLog(input_ or common_globals.log)
    key = None
    keymode = settings.get_key_mode()
    past_key = (
        await asyncio.get_event_loop().run_in_executor(
            common_globals.cache_thread, partial(cache.get, ele.license)
        )
        if constants.getattr("USE_CACHE_KEY")
        else None
    )
    if past_key:
        key = past_key
        log.debug(f"{get_medialog(ele)} got key from cache")
    if keymode == "manual":
        key = await key_helper_manual(c, item["pssh"], ele.license, ele.id)
    elif keymode == "keydb":
        key = await key_helper_keydb(c, item["pssh"], ele.license, ele.id)
    elif keymode == "cdrm":
        key = await key_helper_cdrm(c, item["pssh"], ele.license, ele.id)
    elif keymode == "cdrm2":
        key = await key_helper_cdrm2(c, item["pssh"], ele.license, ele.id)
    if not key:
        raise Exception(f"{get_medialog(ele)} Could not get key")
    await asyncio.get_event_loop().run_in_executor(
        common_globals.cache_thread,
        partial(cache.set, ele.license, key, expire=constants.getattr("KEY_EXPIRY")),
    )
    log.debug(f"{get_medialog(ele)} got key")
    newpath = pathlib.Path(re.sub("\.part$", "", str(item["path"]), re.IGNORECASE))
    log.debug(
        f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}"
    )
    r = subprocess.run(
        [
            settings.get_mp4decrypt(),
            "--key",
            key,
            str(item["path"]),
            str(newpath),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not pathlib.Path(newpath).exists():
        log.debug(f"{get_medialog(ele)} mp4decrypt failed")
        log.debug(f"{get_medialog(ele)} mp4decrypt {r.stderr.decode()}")
        log.debug(f"{get_medialog(ele)} mp4decrypt {r.stdout.decode()}")
    else:
        log.debug(f"{get_medialog(ele)} mp4decrypt success {newpath}")
    pathlib.Path(item["path"]).unlink(missing_ok=True)
    item["path"] = newpath
    return item


async def key_helper_cdrm(c, pssh, licence_url, id):
    log.debug(f"ID:{id} using cdrm auto key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        headers = auth_requests.make_headers()
        headers["cookie"] = auth_requests.get_cookies()
        auth_requests.create_sign(licence_url, headers)
        json_data = {
            "license": licence_url,
            "headers": json.dumps(headers),
            "pssh": pssh,
            "buildInfo": "",
            "proxy": "",
            "cache": True,
        }
        async with c.requests_async(
            url=constants.getattr("CDRM"),
            method="post",
            json=json_data,
            retries=constants.getattr("CDM_RETRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as r:
            httpcontent = await r.text_()
            log.debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, "html.parser")
            out = soup.find("li").contents[0]
        return out
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def key_helper_cdrm2(c, pssh, licence_url, id):
    log.debug(f"ID:{id} using cdrm2 auto key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        headers = auth_requests.make_headers()
        headers["cookie"] = auth_requests.get_cookies()
        auth_requests.create_sign(licence_url, headers)
        json_data = {
            "license": licence_url,
            "headers": json.dumps(headers),
            "pssh": pssh,
            "buildInfo": "google/sdk_gphone_x86/generic_x86:8.1.0/OSM1.180201.037/6739391:userdebug/dev-keys",
            "proxy": "",
            "cache": True,
        }
        async with c.requests_async(
            url=constants.getattr("CDRM2"),
            method="post",
            json=json_data,
            retries=constants.getattr("CDM_RETRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as r:
            httpcontent = await r.text_()
            log.debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, "html.parser")
            out = soup.find("li").contents[0]
        return out
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def key_helper_keydb(c, pssh, licence_url, id):
    log.debug(f"ID:{id} using keydb auto key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        headers = auth_requests.make_headers()
        headers["cookie"] = auth_requests.get_cookies()
        auth_requests.create_sign(licence_url, headers)
        json_data = {
            "license_url": licence_url,
            "headers": json.dumps(headers),
            "pssh": pssh,
            "buildInfo": "",
            "proxy": "",
            "cache": True,
        }

        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Ktesttemp, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
            "Content-Type": "application/json",
            "X-API-Key": config_data.get_keydb_api(),
        }

        async with c.requests_async(
            url=constants.getattr("KEYDB"),
            method="post",
            json=json_data,
            headers=headers,
            retries=constants.getattr("CDM_RETRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as r:
            data = await r.json_()
            log.debug(f"keydb json {data}")
            if isinstance(data, str):
                out = data
            elif isinstance(data["keys"][0], str):
                out = data["keys"][0]
            elif isinstance(data["keys"][0], object):
                out = data["keys"][0]["key"]
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread,
                partial(
                    cache.set,
                    licence_url,
                    out,
                    expire=constants.getattr("KEY_EXPIRY"),
                ),
            )
        return out
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def key_helper_manual(c, pssh, licence_url, id):
    log.debug(f"ID:{id}  manual key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")

        # prepare pssh
        pssh_obj = PSSH(pssh)

        # load device
        private_key = pathlib.Path(config_data.get_private_key()).read_bytes()
        client_id = pathlib.Path(config_data.get_client_id()).read_bytes()
        device = Device(
            security_level=3,
            private_key=private_key,
            client_id=client_id,
            type_="ANDROID",
            flags=None,
        )

        # load cdm
        cdm = Cdm.from_device(device)

        # open cdm session
        session_id = cdm.open()

        keys = None
        challenge = cdm.get_license_challenge(session_id, pssh_obj)
        async with sessionManager.sessionManager(
            backend="httpx", sem=common_globals.sem
        ) as c:
            async with c.requests_async(
                url=licence_url,
                method="post",
                data=challenge,
                retries=constants.getattr("CDM_RETRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
            ) as r:
                cdm.parse_license(session_id, (await r.read_()))
                keys = cdm.get_keys(session_id)
                cdm.close(session_id)
            keyobject = list(filter(lambda x: x.type == "CONTENT", keys))[0]

        key = "{}:{}".format(keyobject.kid.hex, keyobject.key.hex())
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

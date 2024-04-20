r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
import json
import sys
import traceback
import logging
import ofscraper.utils.args as args_
import ofscraper.actions.process as process_actions
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.menu as menu
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.run as run
import ofscraper.utils.system.network as network
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.constants as constants

log=logging.getLogger("shared")

def print_start():
    with stdout.lowstdout():
        console.get_shared_console().print(
            f"[bold green]Version {read_args.retriveArgs().version}[/bold green]"
        )

def main():
    try:
        print_start()
        paths.temp_cleanup()
        paths.cleanDB()
        network.check_cdm()

        print('in main before request');
        asyncio.run(request())
        print('in main after request');

        paths.temp_cleanup()
        paths.cleanDB()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E

async def request():
    print('top of request');
    args = read_args.retriveArgs()
    with sessionManager.sessionManager(
        backend="httpx",
        limit=constants.getattr("API_MAX_CONNECTION"),
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        print("url=", args.get("url"))
        print("method=", args.get("method").lower())

        with c.requests(url = args.get("url"), method = args.get("method").lower) as r:
            print("request completed")
            if r.ok:
                print("r is ok")
                body = await r.text_()
                print(body)
            else:
                print("r is not ok")
                print(json.dumps({
                     '__OF_SCRAPER_STATUS__': 'ERROR',
                     'status': r.status,
                     'body': await r.text_()
                }))
                sys.exit(1)
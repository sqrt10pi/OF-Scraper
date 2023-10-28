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
import ofscraper.utils.paths as paths
import ofscraper.utils.exit as exit
import ofscraper.utils.args as args_
import ofscraper.utils.exit as exit
import ofscraper.utils.misc as misc
import ofscraper.classes.sessionbuilder as sessionbuilder

log=logging.getLogger("shared")

def main():
        try:
            paths.cleanup()
            paths.cleanDB()
            misc.check_cdm()
            asyncio.run(request())
            paths.cleanup()
            paths.cleanDB()
        except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    paths.cleanup()
                    paths.cleanDB()
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                    raise KeyboardInterrupt
        except Exception as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    paths.cleanup()
                    paths.cleanDB()
                    log.traceback(E)
                    log.traceback(traceback.format_exc())
                    raise E
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    raise E

async def request():
    async with sessionbuilder.sessionBuilder()  as c:
        async with c.requests(url=args_.getargs().url, method=args_.getargs().method.lower())() as r:
            if r.ok:
                body = await r.text_()
                print(body)
            else:
                print(json.dumps({
                     '__OF_SCRAPER_STATUS__': 'ERROR',
                     'status': r.status,
                     'body': await r.text_()
                }))
                sys.exit(1)
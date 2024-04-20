import logging
import time
import traceback

import httpx

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.settings as settings


def check_cdm():
    with stdout.lowstdout():
        console = console_.get_shared_console()
        log = logging.getLogger("shared")

        keymode = settings.get_key_mode()
        console.print(f"[yellow]Key Mode: {keymode}\n\n[/yellow]")
        if keymode == "manual":
            console.print(
                "[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/yellow]"
            )
            return True
        elif keymode == "keydb":
            url = constants.getattr("KEYDB")
        elif keymode == "cdrm":
            url = constants.getattr("CDRM")
        elif keymode == "cdrm2":
            url = constants.getattr("CDRM2")
        try:
            with sessionManager.sessionManager(
                backend="httpx",
                total_timeout=30,
                retries=constants.getattr("CDM_NUM_TRIES"),
                wait_min=constants.getattr("CDM_MIN_WAIT"),
                wait_max=constants.getattr("CDM_MAX_WAIT"),
            ) as c:
                with c.requests(url=url) as r:
                    if r.ok:
                        console.print(
                            "[green] CDM service seems to be working\n[/green]"
                        )
                        console.print(
                            "[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/yellow]"
                        )
                        return True
                    else:
                        console.print(
                            "[red]CDM return an error\nThis may cause a lot of failed downloads\n consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]"
                        )
                        log.debug(f"[bold] cdm status[/bold]: {r.status}")
                        log.debug(f"[bold]  cdm text [/bold]: {r.text_()}")
                        log.debug(f"[bold]  cdm headers [/bold]: {r.headers}")
                        time.sleep(3.5)
                        return False
        except httpx.TimeoutException as E:
            console.print(
                f"[red]CDM service {keymode} timed out and seems to be down\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]"
            )
            log.debug(traceback.format_exc())
            time.sleep(3.5)

        except Exception as E:
            console.print(
                f"[red]CDM service {keymode} has an issue {E}\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]"
            )
            log.debug(traceback.format_exc())
            time.sleep(3.5)
        return False

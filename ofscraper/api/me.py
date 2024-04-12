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

import logging
import traceback

from tenacity import (
    Retrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.constants as constants
import ofscraper.utils.logs.helpers as log_helpers

log = logging.getLogger("shared")


def scrape_user():
    with sessionbuilder.sessionBuilder(
        backend="httpx",
        limit=constants.getattr("API_MAX_CONNECTION"),
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_AUTH_MIN_WAIT"),
        wait_max=constants.getattr("OF_AUTH_MAX_WAIT"),
    ) as c:
        return _scraper_user_helper(c)


def _scraper_user_helper(c):
    try:
        with c.requests(constants.getattr("meEP")) as r:
            data = r.json_()
            log_helpers.updateSenstiveDict(data["id"], "userid")
            log_helpers.updateSenstiveDict(
                f"{data['username']} | {data['username']}|\\b{data['username']}\\b",
                "username",
            )
            log_helpers.updateSenstiveDict(
                f"{data['name']} | {data['name']}|\\b{data['name']}\\b",
                "name",
            )

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    return data


def parse_subscriber_count():
    with sessionbuilder.sessionBuilder(
        backend="httpx",
        limit=constants.getattr("API_MAX_CONNECTION"),
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT"),
        wait_max=constants.getattr("OF_MAX_WAIT"),
    ) as c:
        try:
            with c.requests(constants.getattr("subscribeCountEP")) as r:
                data = r.json_()
                return (
                    data["subscriptions"]["active"],
                    data["subscriptions"]["expired"],
                )

        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            raise E

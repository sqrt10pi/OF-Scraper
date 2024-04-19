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
import contextvars
import logging
import traceback

import arrow

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


@run
async def get_messages_progress(model_id, username, forced_after=None, c=None):
    global after

    oldmessages = (
        await operations.get_messages_post_info(model_id=model_id, username=username)
        if not read_args.retriveArgs().no_cache
        else []
    )

    log.trace(
        "oldmessage {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"oldmessages: {str(x)}", oldmessages))
            )
        )
    )
    before = (read_args.retriveArgs().before or arrow.now()).float_timestamp
    after = await get_after(model_id, username, forced_after)

    log.debug(f"Messages after = {after}")

    log.debug(f"Messages before = {before}")

    log.info(
        f"""
Setting initial message scan date for {username} to {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))}
[yellow]Hint: append ' --after 2000' to command to force scan of all messages + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all messages + download/re-download of all files[/yellow]

        """
    )

    filteredArray = get_filterArray(after, before, oldmessages)
    splitArrays = get_split_array(filteredArray)
    tasks = get_tasks(splitArrays, filteredArray, oldmessages, model_id, c)
    data = await process_tasks(tasks, model_id)
    progress_utils.messages_layout.visible = False
    return data


@run
async def get_messages(model_id, username, forced_after=None, c=None):
    global after

    oldmessages = (
        await operations.get_messages_post_info(model_id=model_id, username=username)
        if not read_args.retriveArgs().no_cache
        else []
    )
    log.trace(
        "oldmessage {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"oldmessages: {str(x)}", oldmessages))
            )
        )
    )

    before = (read_args.retriveArgs().before or arrow.now()).float_timestamp
    after = await get_after(model_id, username, forced_after)

    log.debug(f"Messages after = {after}")

    log.debug(f"Messages before = {before}")

    log.info(
        f"""
Setting initial message scan date for {username} to {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))}
[yellow]Hint: append ' --after 2000' to command to force scan of all messages + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all messages + download/re-download of all files[/yellow]

        """
    )

    filteredArray = get_filterArray(after, before, oldmessages)
    splitArrays = get_split_array(filteredArray)
    with progress_utils.set_up_api_messages():
        tasks = get_tasks(splitArrays, filteredArray, oldmessages, model_id, c)
        return await process_tasks(tasks, model_id)


async def process_tasks(tasks, model_id):
    page_count = 0
    responseArray = []
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f" Message Content Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        try:
            for task in asyncio.as_completed(
                tasks, timeout=constants.getattr("API_TIMEOUT_PER_TASK")
            ):
                try:
                    result, new_tasks_batch = await task
                    new_tasks.extend(new_tasks_batch)
                    page_count = page_count + 1
                    overall_progress.update(
                        page_task,
                        description=f"Message Content Pages Progress: {page_count}",
                    )
                    new_posts = [
                        post
                        for post in result
                        if post["id"] not in seen and not seen.add(post["id"])
                    ]
                    log.debug(
                        f"{common_logs.PROGRESS_IDS.format('Messages')} {list(map(lambda x:x['id'],new_posts))}"
                    )
                    log.trace(
                        f"{common_logs.PROGRESS_RAW.format('Messages')}".format(
                            posts="\n\n".join(
                                list(
                                    map(
                                        lambda x: f"{common_logs.RAW_INNER} {x}",
                                        new_posts,
                                    )
                                )
                            )
                        )
                    )

                    responseArray.extend(new_posts)
                except asyncio.TimeoutError:
                    log.traceback_("Task timed out")
                    log.traceback_(traceback.format_exc())
                    [ele.cancel() for ele in tasks]
                    break
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    continue
        except asyncio.TimeoutError:
            log.traceback_("Task timed out")
            log.traceback_(traceback.format_exc())
            [ele.cancel() for ele in tasks]
        tasks = new_tasks

    overall_progress.remove_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Messages')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.trace(
        f"{common_logs.FINAL_RAW.format('Messages')}".format(
            posts="\n\n".join(
                list(map(lambda x: f"{common_logs.RAW_INNER} {x}", responseArray))
            )
        )
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Messages')} {len(responseArray)}")

    set_check(responseArray, model_id, after)
    return responseArray


def get_filterArray(after, before, oldmessages):
    oldmessages = list(filter(lambda x: (x.get("created_at")) != None, oldmessages))
    log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")
    oldmessages = sorted(
        oldmessages,
        key=lambda x: x.get("created_at"),
        reverse=True,
    )
    if after > before:
        return []
    elif len(oldmessages) <= 2:
        return oldmessages
    else:
        return oldmessages[get_i(oldmessages, before) : get_j(oldmessages, after)]


def get_i(oldmessages, before):
    """
    iterate through posts until a date less then or equal
    to before , set index to -1 this point
    """
    if before >= oldmessages[1].get("created_at"):
        return 0
    if before <= oldmessages[-1].get("created_at"):
        return len(oldmessages) - 2
    # Use a generator expression for efficiency
    return max(
        next(
            index - 1
            for index, message in enumerate(oldmessages)
            if message.get("created_at") <= before
        ),
        0,
    )


def get_j(oldmessages, after):
    """
    iterate through posts until a date less then or equal
    to after , set index to +1 this point
    """
    if after >= oldmessages[0].get("created_at"):
        return 0
    if after <= oldmessages[-1].get("created_at"):
        return len(oldmessages)
    return min(
        next(
            index + 1
            for index, message in enumerate(oldmessages)
            if message.get("created_at") <= after
        ),
        len(oldmessages) - 1,
    )


def get_split_array(filteredArray):
    min_posts = 50
    return [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]


def get_tasks(splitArrays, filteredArray, oldmessages, model_id, c):
    tasks = []
    job_progress = progress_utils.messages_progress

    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    job_progress=job_progress,
                    message_id=(
                        splitArrays[0][0].get("post_id")
                        if len(filteredArray) == len(oldmessages)
                        else None
                    ),
                    required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                )
            )
        )
        [
            tasks.append(
                asyncio.create_task(
                    scrape_messages(
                        c,
                        model_id,
                        job_progress=job_progress,
                        message_id=splitArrays[i - 1][-1].get("post_id"),
                        required_ids=set(
                            [ele.get("created_at") for ele in splitArrays[i]]
                        ),
                    )
                )
            )
            for i in range(1, len(splitArrays) - 1)
        ]
        # keeping grabbing until nothing left
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    job_progress=job_progress,
                    message_id=splitArrays[-2][-1].get("post_id"),
                    required_ids=set(
                        [ele.get("created_at") for ele in splitArrays[-1]]
                    ),
                )
            )
        )
    # use the first split if less then 3
    elif len(splitArrays) > 0:
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    job_progress=job_progress,
                    required_ids=None,
                    message_id=(
                        splitArrays[0][0].get("post_id")
                        if len(filteredArray) == len(oldmessages)
                        else None
                    ),
                )
            )
        )
    # set init message to none
    else:
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    job_progress=job_progress,
                    message_id=None,
                    required_ids=None,
                )
            )
        )
    return tasks


def set_check(unduped, model_id, after):
    if not after:
        seen = set()
        all_posts = [
            post
            for post in cache.get(f"message_check_{model_id}", default=[]) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        cache.set(
            f"message_check_{model_id}",
            list(all_posts),
            expire=constants.getattr("DAY_SECONDS"),
        )
        cache.close()


async def scrape_messages(
    c, model_id, job_progress=None, message_id=None, required_ids=None
) -> list:
    messages = None
    attempt.set(0)
    ep = (
        constants.getattr("messagesNextEP")
        if message_id
        else constants.getattr("messagesEP")
    )
    url = ep.format(model_id, message_id)
    log.debug(f"{message_id if message_id else 'init'} {url}")
    new_tasks = []
    await asyncio.sleep(1)
    try:
        async with c.requests_async(url=url) as r:
            attempt.set(attempt.get(0) + 1)

            task = (
                job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')}: Message ID-> {message_id if message_id else 'initial'}"
                )
                if job_progress
                else None
            )
            messages = (await r.json_())["list"]
            log_id = f"offset messageid:{message_id if message_id else 'init id'}"
            if not messages:
                messages = []
            if len(messages) == 0:
                log.debug(f"{log_id} -> number of messages found 0")
            elif len(messages) > 0:
                log.debug(f"{log_id} -> number of messages found {len(messages)}")
                log.debug(
                    f"{log_id} -> first date {arrow.get(messages[-1].get('createdAt') or messages[0].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
                )
                log.debug(
                    f"{log_id} -> last date {arrow.get(messages[-1].get('createdAt') or messages[0].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
                )
                log.debug(
                    f"{log_id} -> found message ids {list(map(lambda x:x.get('id'),messages))}"
                )
                log.trace(
                    "{log_id} -> messages raw {posts}".format(
                        log_id=log_id,
                        posts="\n\n".join(
                            list(
                                map(
                                    lambda x: f" messages scrapeinfo: {str(x)}",
                                    messages,
                                )
                            )
                        ),
                    )
                )
                timestamp = arrow.get(
                    messages[-1].get("createdAt") or messages[-1].get("postedAt")
                ).float_timestamp

                if timestamp < after:
                    attempt.set(0)
                elif required_ids is None:
                    attempt.set(0)
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_messages(
                                c,
                                model_id,
                                job_progress=job_progress,
                                message_id=messages[-1]["id"],
                            )
                        )
                    )
                else:
                    [
                        required_ids.discard(
                            arrow.get(ele.get("createdAt") or ele.get("postedAt")).float_timestamp
                        )
                        for ele in messages
                    ]

                    if len(required_ids) > 0 and timestamp > min(list(required_ids)):
                        attempt.set(0)
                        new_tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c,
                                    model_id,
                                    job_progress=job_progress,
                                    message_id=messages[-1]["id"],
                                    required_ids=required_ids,
                                )
                            )
                        )
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    finally:
        (job_progress.remove_task(task) if job_progress and task != None else None)
    return messages, new_tasks


def get_individual_post(model_id, postid):
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        with c.requests(
            url=constants.getattr("messageSPECIFIC").format(model_id, postid)
        ) as r:
            log.trace(f"message raw individual {r.json()}")
            return r.json()["list"][0]


async def get_after(model_id, username, forced_after=None):
    if forced_after != None:
        return forced_after
    elif not settings.get_after_enabled():
        return 0
    elif read_args.retriveArgs().after == 0:
        return 0
    elif read_args.retriveArgs().after:
        return read_args.retriveArgs().after.float_timestamp
    elif cache.get(f"{model_id}_scrape_messages"):
        log.debug(
            "Used --after previously. Scraping all messages required to make sure content is not missing"
        )
        return 0
    curr = await operations.get_messages_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    missing_items = list(filter(lambda x: x.get("downloaded") != 1, curr))
    missing_items = list(
        sorted(missing_items, key=lambda x: arrow.get(x.get("posted_at") or 0))
    )
    if len(missing_items) == 0:
        log.debug(
            "Using last db date because,all downloads in db are marked as downloaded"
        )
        return arrow.get(
            await operations.get_last_message_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} messages in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0].get("posted_at") or 0).float_timestamp

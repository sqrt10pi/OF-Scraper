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
from concurrent.futures import ThreadPoolExecutor

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


@run
async def get_otherlist():
    out = []
    if any(
        [
            ele
            not in [
                constants.getattr("OFSCRAPER_RESERVED_LIST"),
                constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
            ]
            for ele in read_args.retriveArgs().user_list or []
        ]
    ):
        out.extend(await get_lists())
    out = list(
        filter(
            lambda x: x.get("name").lower() in read_args.retriveArgs().user_list or [],
            out,
        )
    )
    log.debug(
        f"User lists found on profile {list(map(lambda x:x.get('name').lower(),out))}"
    )
    return await get_list_users(out)


@run
async def get_blacklist():
    out = []
    if len(read_args.retriveArgs().black_list or []) >= 1:
        out.extend(await get_lists())
    out = list(
        filter(
            lambda x: x.get("name").lower() in read_args.retriveArgs().black_list or [],
            out,
        )
    )
    log.debug(
        f"Black lists found on profile {list(map(lambda x:x.get('name').lower(),out))}"
    )
    names = list(await get_list_users(out))
    return set(list(map(lambda x: x["id"], names)))


async def get_lists():
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting lists...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        tasks = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
            ) as c:
                tasks.append(asyncio.create_task(scrape_for_list(c, job_progress)))
                page_task = overall_progress.add_task(
                    f"UserList Pages Progress: {page_count}", visible=True
                )
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
                                description=f"UserList Pages Progress: {page_count}",
                            )
                            output.extend(result)
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
        log.trace(
            "list unduped {posts}".format(
                posts="\n\n".join(map(lambda x: f" list data raw:{x}", output))
            )
        )
        log.debug(f"[bold]lists name count without Dupes[/bold] {len(output)} found")
        return output


async def scrape_for_list(c, job_progress, offset=0):
    attempt.set(0)
    new_tasks = []
    try:
        attempt.set(attempt.get(0) + 1)
        task = job_progress.add_task(
            f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')} : getting lists offset -> {offset}",
            visible=True,
        )
        async with c.requests_async(
            url=constants.getattr("listEP").format(offset)
        ) as r:
            data = await r.json_()
            out_list = data["list"] or []
            log.debug(
                f"offset:{offset} -> lists names found {list(map(lambda x:x['name'],out_list))}"
            )
            log.debug(f"offset:{offset} -> number of lists found {len(out_list)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.trace(
                "offset:{offset} -> label names raw: {posts}".format(
                    offset=offset, posts=data
                )
            )

            if data.get("hasMore") and len(out_list) > 0:
                offset = offset + len(out_list)
                new_tasks.append(
                    asyncio.create_task(scrape_for_list(c, job_progress, offset=offset))
                )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task)
    return out_list, new_tasks


async def get_list_users(lists):
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn(
                "Getting users from lists (this may take awhile)...\n{task.description}"
            ),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        tasks = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
            ) as c:
                [
                    tasks.append(
                        asyncio.create_task(scrape_list_members(c, id, job_progress))
                    )
                    for id in lists
                ]
                page_task = overall_progress.add_task(
                    f"UserList Users Pages Progress: {page_count}", visible=True
                )
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
                                description=f"UserList Users Pages Progress: {page_count}",
                            )
                            output.extend(result)
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
    outdict = {}
    for ele in output:
        outdict[ele["id"]] = ele
    log.trace(
        "users found {users}".format(
            users="\n\n".join(
                list(map(lambda x: f"user data: {str(x)}", outdict.values()))
            )
        )
    )
    log.debug(f"[bold]users count without Dupes[/bold] {len(outdict.values())} found")
    return outdict.values()


async def scrape_list_members(c, item, job_progress, offset=0):
    users = None
    attempt.set(0)
    new_tasks = []
    try:
        attempt.set(attempt.get(0) + 1)
        task = job_progress.add_task(
            f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')} : offset -> {offset} + list name -> {item.get('name')}",
            visible=True,
        )

        async with c.requests_async(
            url=constants.getattr("listusersEP").format(item.get("id"), offset)
        ) as r:
            log_id = f"offset:{offset} list:{item.get('name')} =>"
            data = await r.json_()
            users = data.get("list") or []
            log.debug(f"{log_id} -> names found {len(users)}")
            log.debug(
                f"{log_id}  -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.debug(
                f"usernames {log_id} : usernames retrived -> {list(map(lambda x:x.get('username'),users))}"
            )
            log.trace(
                "offset: {offset} list: {item} -> {posts}".format(
                    item=item.get("name"),
                    offset=offset,
                    posts="\n\n".join(
                        list(map(lambda x: f"scrapeinfo list {str(x)}", users))
                    ),
                )
            )
            if (
                data.get("hasMore")
                and len(users) > 0
                and offset != data.get("nextOffset")
            ):
                offset += len(users)
                new_tasks.append(
                    asyncio.create_task(
                        scrape_list_members(c, item, job_progress, offset=offset)
                    )
                )
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task)
    return users, new_tasks

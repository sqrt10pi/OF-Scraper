import asyncio
import inspect
import logging
import queue
import re
import threading
import time
import traceback

import arrow

import ofscraper.api.archive as archived
import ofscraper.api.highlights as highlights
import ofscraper.api.labels as labels
import ofscraper.api.messages as messages_
import ofscraper.api.paid as paid_
import ofscraper.api.pinned as pinned
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.classes.table as table
import ofscraper.db.operations as operations
import ofscraper.download.downloadnormal as downloadnormal
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
import ofscraper.utils.system.network as network
from ofscraper.download.common.common import textDownloader
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
console = console_.get_shared_console()
ROW_NAMES = (
    "Number",
    "Download_Cart",
    "UserName",
    "Downloaded",
    "Unlocked",
    "Times_Detected",
    "Length",
    "Mediatype",
    "Post_Date",
    "Post_Media_Count",
    "Responsetype",
    "Price",
    "Post_ID",
    "Media_ID",
    "Text",
)
ROWS = []
app = None
prev_names = prev_names = set()
ALL_MEDIA = {}


def process_download_cart():
    while True:
        global app
        if not app or app.row_queue.empty():
            time.sleep(10)
            continue
        try:
            process_item()
        except Exception as E:
            # handle getting new downloads
            None


def process_item():
    global app
    if process_download_cart.counter == 0:
        if not network.check_cdm():
            log.info("error was raised by cdm checker\ncdm will not be check again\n\n")
        else:
            log.info("cdm checker was fine\ncdm will not be check again\n\n")
        # should be done once before downloads
        log.info("Getting Models")

    process_download_cart.counter = process_download_cart.counter + 1
    log.info("Getting items from cart")
    try:
        row, key = app.row_queue.get()
        username = row[app.row_names.index("UserName")].plain
        post_id = row[app.row_names.index("Post_ID")].plain
        media_id = int(row[app.row_names.index("Media_ID")].plain)

        media = ALL_MEDIA.get(f"{media_id}_{post_id}_{username}")
        if not media:
            raise Exception(f"No data for {media_id}_{post_id}_{username}")

        log.info(f"Added url {media.url or media.mpd}")
        log.info("Sending URLs to OF-Scraper")
        selector.set_data_all_subs_dict(username)
        post = media.post
        if settings.get_mediatypes() == ["Text"]:
            textDownloader(post, username=username)
        elif len(settings.get_mediatypes()) > 1:
            model_id = media.post.model_id
            username = model_id = media.post.username
            log.info(
                f"Downloading individual media ({media.filename}) to disk for {username}"
            )
            operations.table_init_create(model_id=model_id, username=username)

            textDownloader(post, username=username)

            values = downloadnormal.process_dicts(username, model_id, [media])
            if values == None or values[-1] == 1:
                raise Exception("Download is marked as skipped")
        else:
            raise Exception("Issue getting download")

        log.info("Download Finished")
        app.update_cell(key, "Download_Cart", "[downloaded]")
        app.update_cell(key, "Downloaded", True)

    except Exception as E:
        app.update_downloadcart_cell(key, "[failed]")
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    if app.row_queue.empty():
        log.info("Download cart is currently empty")


def checker():
    args = read_args.retriveArgs()
    if args.command == "post_check":
        post_checker()
    elif args.command == "msg_check":
        message_checker()
    elif args.command == "paid_check":
        purchase_checker()
    elif args.command == "story_check":
        stories_checker()


def post_checker():
    post_check_helper()
    start_helper()


@run
async def post_check_helper():
    user_dict = {}
    links = list(url_helper())
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        for ele in links:
            name_match = re.search(
                f"onlyfans.com/({constants.getattr('USERNAME_REGEX')}+$)", ele
            )
            name_match2 = re.search(f"^{constants.getattr('USERNAME_REGEX')}+$", ele)
            user_name = None
            model_id = None

            if name_match:
                user_name = name_match.group(1)
                log.info(f"Getting Full Timeline for {user_name}")
                model_id = profile.get_id(user_name)
                user_dict.setdefault(model_id, {})["model_id"] = model_id
                user_dict.setdefault(model_id, {})["username"] = user_name

            elif name_match2:
                user_name = name_match2.group(0)
                model_id = profile.get_id(user_name)
                user_dict.setdefault(model_id, {})["model_id"] = model_id
                user_dict.setdefault(model_id, {})["username"] = user_name
            if user_dict.get(model_id) and model_id and user_name:
                areas = read_args.retriveArgs().check_area
                await operations.table_init_create(
                    username=user_name, model_id=model_id
                )
                if "Timeline" in areas:
                    oldtimeline = cache.get(f"timeline_check_{model_id}", default=[])
                    if len(oldtimeline) > 0 and not read_args.retriveArgs().force:
                        data = oldtimeline
                    else:
                        data = await timeline.get_timeline_posts(
                            model_id, user_name, forced_after=0, c=c
                        )
                    user_dict.setdefault(model_id, {}).setdefault(
                        "post_list", []
                    ).extend(data)
                if "Archived" in areas:
                    oldarchive = cache.get(f"archived_check_{model_id}", default=[])
                    if len(oldarchive) > 0 and not read_args.retriveArgs().force:
                        data = oldarchive
                    else:
                        data = await archived.get_archived_posts(
                            model_id, user_name, forced_after=0, c=c
                        )
                    user_dict.setdefault(model_id, {}).setdefault(
                        "post_list", []
                    ).extend(data)
                if "Pinned" in areas:
                    oldpinned = cache.get(f"pinned_check_{model_id}", default=[])
                    if len(oldpinned) > 0 and not read_args.retriveArgs().force:
                        data = oldpinned
                    else:
                        data = await pinned.get_pinned_posts(model_id, c=c)
                    user_dict.setdefault(model_id, {}).setdefault(
                        "post_list", []
                    ).extend(data)
                if "Labels" in areas:
                    oldlabels = cache.get(f"labels_check_{model_id}", default=[])
                    if len(oldlabels) > 0 and not read_args.retriveArgs().force:
                        data = oldlabels
                    else:
                        labels_data = await labels.get_labels(model_id, c=c)
                        await operations.make_label_table_changes(
                            labels_data,
                            model_id=model_id,
                            username=user_name,
                            posts=False,
                        )
                        data = [
                            post for label in labels_data for post in label["posts"]
                        ]
                    user_dict.setdefault(model_id, {}).setdefault(
                        "post_list", []
                    ).extend(data)
                cache.close()
        # individual links
        for ele in list(
            filter(
                lambda x: re.search(
                    f"onlyfans.com/{constants.getattr('NUMBER_REGEX')}+/{constants.getattr('USERNAME_REGEX')}+$",
                    x,
                ),
                links,
            )
        ):
            name_match = re.search(f"/({constants.getattr('USERNAME_REGEX')}+$)", ele)
            num_match = re.search(f"/({constants.getattr('NUMBER_REGEX')}+)", ele)
            if name_match and num_match:
                user_name = name_match.group(1)
                model_id = profile.get_id(user_name)
                user_dict.setdefault(model_id, {})["model_id"] = model_id
                user_dict.setdefault(model_id, {})["username"] = user_name

                post_id = num_match.group(1)
                log.info(f"Getting individual link for {user_name}")
                data = timeline.get_individual_post(post_id)
                user_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    data
                )
    for val in user_dict.values():
        user_name = val.get("username")
        downloaded = await get_downloaded(user_name, model_id, True)
        posts = list(
            map(lambda x: posts_.Post(x, model_id, user_name), val.get("post_list", []))
        )
        await operations.make_post_table_changes(
            posts, model_id=model_id, username=user_name
        )
        await process_post_media(user_name, model_id, posts)
        row_gather(downloaded, user_name)


def reset_url():
    # clean up args once check modes are ready to launch
    args = read_args.retriveArgs()
    argdict = vars(args)
    if argdict.get("url"):
        read_args.retriveArgs().url = None
    if argdict.get("file"):
        read_args.retriveArgs().file = None
    if argdict.get("username"):
        read_args.retriveArgs().usernames = None
    write_args.setArgs(args)


def set_count(ROWS):
    for count, ele in enumerate(ROWS):
        ele[0] = count + 1


def start_helper():
    global ROWS
    reset_url()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def message_checker():
    message_checker_helper()
    start_helper()


@run
async def message_checker_helper():
    links = list(url_helper())
    async with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        for item in links:
            num_match = re.search(
                f"({constants.getattr('NUMBER_REGEX')}+)", item
            ) or re.search(f"^({constants.getattr('NUMBER_REGEX')}+)$", item)
            name_match = re.search(f"^{constants.getattr('USERNAME_REGEX')}+$", item)
            if num_match:
                model_id = num_match.group(1)
                user_name = profile.scrape_profile(model_id)["username"]
            elif name_match:
                user_name = name_match.group(0)
                model_id = profile.get_id(user_name)
            if model_id and user_name:
                log.info(f"Getting Messages/Paid content for {user_name}")
                await operations.table_init_create(
                    model_id=model_id, username=user_name
                )
                # messages
                messages = None
                oldmessages = cache.get(f"message_check_{model_id}", default=[])
                log.debug(f"Number of messages in cache {len(oldmessages)}")

                if len(oldmessages) > 0 and not read_args.retriveArgs().force:
                    messages = oldmessages
                else:
                    messages = await messages_.get_messages(
                        model_id, user_name, forced_after=0, c=c
                    )
                message_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), messages)
                )
                await operations.make_messages_table_changes(
                    message_posts_array, model_id=model_id, username=user_name
                )

                oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
                paid = None
                # paid content
                if len(oldpaid) > 0 and not read_args.retriveArgs().force:
                    paid = oldpaid
                else:
                    paid = await paid_.get_paid_posts(model_id, user_name, c=c)
                paid_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), paid)
                )
                await operations.make_changes_to_content_tables(
                    paid_posts_array, model_id=model_id, username=user_name
                )

                await process_post_media(
                    user_name, model_id, paid_posts_array + message_posts_array
                )

                downloaded = await get_downloaded(user_name, model_id, True)

                row_gather(downloaded, user_name)


def purchase_checker():
    purchase_checker_helper()
    start_helper()


@run
async def purchase_checker_helper():
    user_dict = {}
    auth_requests.make_headers()
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        for name in read_args.retriveArgs().usernames:
            user_name = profile.scrape_profile(name)["username"]
            model_id = name if name.isnumeric() else profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(model_id, [])

            await operations.table_init_create(model_id=model_id, username=user_name)

            oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
            paid = None

            if len(oldpaid) > 0 and not read_args.retriveArgs().force:
                paid = oldpaid
            if user_name == constants.getattr("DELETED_MODEL_PLACEHOLDER"):
                all_paid = await paid_.get_all_paid_posts()
                paid_user_dict = {}
                for ele in all_paid:
                    # Get the user ID from either "fromUser" or "author" key (handle missing keys)
                    user_id = (
                        ele.get("fromUser", None) or ele.get("author", None) or {}
                    ).get("id", None)

                    # If user_id is found, update the paid_user_dict
                    if user_id:
                        paid_user_dict.setdefault(str(user_id), []).append(ele)
                seen = set()
                paid = [
                    post
                    for post in paid_user_dict.get(str(model_id), [])
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
            else:
                paid = await paid_.get_paid_posts(model_id, user_name, c=c)
            posts_array = list(map(lambda x: posts_.Post(x, model_id, user_name), paid))
            await operations.make_changes_to_content_tables(
                posts_array, model_id=model_id, username=user_name
            )
            downloaded = await get_downloaded(user_name, model_id)
            await process_post_media(user_name, model_id, posts_array)
            row_gather(downloaded, user_name)


def stories_checker():
    stories_checker_helper()
    start_helper()


@run
async def stories_checker_helper():
    user_dict = {}
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        for user_name in read_args.retriveArgs().usernames:
            user_name = profile.scrape_profile(user_name)["username"]
            model_id = profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(user_name, [])
            await operations.table_init_create(model_id=model_id, username=user_name)
            stories = await highlights.get_stories_post(model_id, c=c)
            highlights_ = await highlights.get_highlight_post(model_id, c=c)
            highlights_ = list(
                map(
                    lambda x: posts_.Post(x, model_id, user_name, "highlights"),
                    highlights_,
                )
            )
            stories = list(
                map(lambda x: posts_.Post(x, model_id, user_name, "stories"), stories)
            )
            downloaded = await get_downloaded(user_name, model_id)
            await process_post_media(user_name, model_id, stories + highlights_)
            row_gather(downloaded, user_name)


def url_helper():
    out = []
    out.extend(read_args.retriveArgs().file or [])
    out.extend(read_args.retriveArgs().url or [])
    return map(lambda x: x.strip(), out)


@run
async def process_post_media(username, model_id, posts_array):
    seen = set()
    unduped = [
        post
        for post in posts_array
        if (post.id, post.username) not in seen
        and not seen.add((post.id, post.username))
    ]
    temp = []
    [temp.extend(ele.all_media) for ele in unduped]
    await operations.batch_mediainsert(
        temp,
        model_id=model_id,
        username=username,
        downloaded=False,
    )
    new_media = {f"{ele.id}_{ele.postid}_{ele.username}": ele for ele in temp}
    ALL_MEDIA.update(new_media)
    return list(new_media.values())


@run
async def get_downloaded(user_name, model_id, paid=False):
    downloaded = {}

    await operations.table_init_create(model_id=model_id, username=user_name)
    paid = await get_paid_ids(model_id, user_name) if paid else []
    [
        downloaded.update({ele: downloaded.get(ele, 0) + 1})
        for ele in operations.get_media_ids_downloaded(
            model_id=model_id, username=user_name
        )
        + paid
    ]

    return downloaded


@run
async def get_paid_ids(model_id, user_name):
    oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
    paid = None

    if len(oldpaid) > 0 and not read_args.retriveArgs().force:
        paid = oldpaid
    else:
        async with sessionManager.sessionManager(
            backend="httpx",
            sem=constants.getattr("API_REQ_CHECK_MAX"),
            retries=constants.getattr("API_CHECK_NUM_TRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as c:
            paid = await paid_.get_paid_posts(model_id, user_name, c=c)
    media = await process_post_media(user_name, model_id, paid)
    media = list(filter(lambda x: x.canview == True, media))
    return list(map(lambda x: x.id, media))


def thread_starters(ROWS_):
    worker_thread = threading.Thread(target=process_download_cart, daemon=True)
    worker_thread.start()
    process_download_cart.counter = 0
    start_table(ROWS_)


def start_table(ROWS_):
    global app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = table.InputApp()
    app.mutex = threading.Lock()
    app.row_queue = queue.Queue()
    ROWS = get_first_row()
    ROWS.extend(ROWS_)

    app.table_data = ROWS
    app.row_names = ROW_NAMES
    app._filtered_rows = app.table_data[1:]
    app.run()


def get_first_row():
    return [ROW_NAMES]


def texthelper(text):
    text = text or ""
    text = inspect.cleandoc(text)
    text = re.sub(" +$", "", text)
    text = re.sub("^ +", "", text)
    text = re.sub("<[^>]*>", "", text)
    text = (
        text
        if len(text) < constants.getattr("TABLE_STR_MAX")
        else f"{text[:constants.getattr('TABLE_STR_MAX')]}..."
    )
    return text


def unlocked_helper(ele):
    return ele.canview


def datehelper(date):
    if date == "None":
        return "Probably Deleted"
    return date


def times_helper(ele, mediadict, downloaded):
    return max(len(mediadict.get(ele.id, [])), downloaded.get(ele.id, 0))


def checkmarkhelper(ele):
    return "[]" if unlocked_helper(ele) else "Not Unlocked"


def row_gather(downloaded, username):
    # fix text
    global ROWS

    mediadict = {}
    [
        mediadict.update({ele.id: mediadict.get(ele.id, []) + [ele]})
        for ele in list(filter(lambda x: x.canview, ALL_MEDIA.values()))
    ]
    out = []
    media_sorted = sorted(
        ALL_MEDIA.values(), key=lambda x: arrow.get(x.date), reverse=True
    )
    for _, ele in enumerate(media_sorted):
        out.append(
            [
                None,
                checkmarkhelper(ele),
                username,
                ele.id in downloaded
                or cache.get(ele.postid) != None
                or cache.get(ele.filename) != None,
                unlocked_helper(ele),
                times_helper(ele, mediadict, downloaded),
                ele.numeric_duration,
                ele.mediatype,
                datehelper(ele.formatted_postdate),
                len(ele._post.post_media),
                ele.responsetype,
                "Free" if ele._post.price == 0 else "{:.2f}".format(ele._post.price),
                ele.postid,
                ele.id,
                texthelper(ele.text),
            ]
        )
    ROWS = ROWS or []
    ROWS.extend(out)

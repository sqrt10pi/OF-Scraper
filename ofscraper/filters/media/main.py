import logging

import ofscraper.filters.media.helpers as helpers

log = logging.getLogger("shared")


def filterMedia(media):
    count = 1
    logformater = "{} data: {} id: {} postid: {}"
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media no filter:",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media no filter count: {len(media)}")
    media = helpers.sort_media(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> final media  from retrived post: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  final media count from retrived post: {len(media)}")
    media = helpers.dupefilter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media dupe filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter {count}-> all media dupe filter count: {len(media)}")
    media = helpers.post_datesorter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 3-> all media datesort: ", x.media, x.id, x.postid
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media datesort count: {len(media)}")
    media = helpers.posts_type_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post media type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter {count}-> all media post media type filter count: {len(media)}")
    media = helpers.posts_date_filter_media(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post date filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media post date filter: {len(media)}")
    media = helpers.post_timed_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all media post timed post filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  all media post timed post filter count: {len(media)}")
    media = helpers.post_user_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post included text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all media post included text filter count: {len(media)}"
    )
    media = helpers.anti_post_user_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post excluded text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all media post excluded text filter count: {len(media)}"
    )
    media = helpers.download_type_filter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all download type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  all media download type filter count: {len(media)}")

    media = helpers.mass_msg_filter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  mass message filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    media = helpers.final_post_sort(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all media final sort: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter{count}-> all media final sort count {len(media)}")

    return media


def filterPost(post):
    count = 1
    logformater = "{} data: {} postid: {}"
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all post no filter:",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all post no filter count: {len(post)}")
    post = helpers.sort_media(post)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> final post  from retrived post: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter {count}->  final post count from retrived post: {len(post)}")
    post = helpers.dupefilter(post)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all post dupe filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )

    log.debug(f"filter {count}-> all post dupe filter count: {len(post)}")
    post = helpers.post_datesorter(post)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 3-> all post datesort: ", x.post, x.id
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all post datesort count: {len(post)}")
    post = helpers.posts_date_filter(post)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all post post date filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all post post date filter: {len(post)}")
    post = helpers.post_timed_filter(post)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all post post timed post filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter {count}->  all post post timed post filter count: {len(post)}")
    post = helpers.post_user_filter(post)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all post post included text filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all post post included text filter count: {len(post)}"
    )
    post = helpers.anti_post_user_filter(post)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all post post excluded text filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all post post excluded text filter count: {len(post)}"
    )

    post = helpers.mass_msg_filter(post)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  mass message filter: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    post = helpers.final_post_sort(post)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all post final sort: ",
                        x.post,
                        x.id,
                    ),
                    post,
                )
            )
        )
    )
    log.debug(f"filter{count}-> all post final sort count {len(post)}")

    return post


def post_filter_for_like(media, like=False):
    media = helpers.post_timed_filter(media)
    post_type = "likable" if like else "unlikable"
    log.debug(
        f"[bold]Number of {post_type} posts left after date filter[/bold] {len(media)}"
    )
    media = helpers.final_post_sort(media)
    media = helpers.ele_count_filter(media)
    log.debug(f"[bold]Final Number of open and {post_type} post[/bold] {len(media)}")
    return media

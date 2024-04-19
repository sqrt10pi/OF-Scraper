import asyncio
import logging
import re
import string

# supress warnings
import warnings

import arrow
from bs4 import MarkupResemblesLocatorWarning
from mpegdash.parser import MPEGDASHParser

import ofscraper.classes.base as base
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.quality as quality
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.helpers as log_helpers

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


log = logging.getLogger("shared")

semaphore = asyncio.Semaphore(constants.getattr("MPD_MAX_SEMS"))


class Media(base.base):
    def __init__(self, media, count, post):
        super().__init__()
        self._media = media
        self._count = count
        self._post = post
        self._final_url = None
        self._cached_parse_mpd = None

    def __eq__(self, other):
        return self.postid == other.postid

    @property
    def expires(self):
        return self._post.expires

    @property
    def media_source(self):
        return self._media.get("source", {})

    @property
    def files_source(self):
        return self._media.get("files", {}).get("source", {})

    @property
    def quality(self):
        return self._media.get("videoSources", {})

    @property
    def mediatype(self):
        if self._media["type"] == "photo":
            return "images"
        elif self._media["type"] == "gif":
            return "videos"
        elif self._media["type"] == "forced_skipped":
            return "forced_skipped"
        else:
            return f"{self._media['type']}s".lower()

    @property
    def duration(self):
        return self._media.get("duration") or self.media_source.get("duration")

    @property
    def numeric_duration(self):
        if not self.duration:
            return "N/A"
        return str((arrow.get(self.duration) - arrow.get(0)))

    @property
    def url(self):
        if self.protected == True:
            return None
        elif self._final_url:
            None
        elif self.responsetype == "stories" or self.responsetype == "highlights":
            self._final_url = self.files_source.get("url")
        elif self.responsetype == "profile":
            self._final_url = self._media.get("url")
        else:
            self._final_url = self._url_source_helper()
        return self._final_url

    def _url_source_helper(self):
        quality = self.normal_quality_helper()
        if quality == "source":
            return self._media.get("source", {}).get("source")
        return self._media.get("videoSources", {}).get(quality)

    @property
    def post(self):
        return self._post

    @property
    def id(self):
        return self._media["id"]

    # ID for use in dynamic names
    @property
    def file_postid(self):
        return self._post._post["id"]

    @property
    def canview(self):
        return self._media.get("canView") if (self.url or self.mpd) != None else False

    @property
    def label(self):
        return self._post.label

    # used for placeholder
    @property
    def label_string(self):
        return self._post.label_string

    @property
    def downloadtype(self):
        return "Protected" if self.mpd else "Normal"

    @property
    def modified_responsetype(self):
        return (
            self._post.modified_response_helper(mediatype=self.mediatype)
            or self._post.modified_responsetype
        )

    @property
    def responsetype(self):
        return self._post.responsetype

    @property
    def value(self):
        return self._post.value

    @property
    def postdate(self):
        return self._post.date

    # modified verison of post date
    @property
    def formatted_postdate(self):
        return self._post.formatted_date

    @property
    def date(self):
        return (
            self._media.get("createdAt") or self._media.get("postedAt") or self.postdate
        )

    # modified verison of media date
    @property
    def formatted_date(self):
        if self._media.get("createdAt") or self._media.get("postedAt"):
            return arrow.get(
                self._media.get("createdAt") or self._media.get("postedAt")
            ).format("YYYY-MM-DD hh:mm:ss")
        return None

    @property
    def id(self):
        return self._media.get("id")

    @property
    def postid(self):
        return self._post.id

    @property
    def text(self):
        return self._post.text

    @property
    def mpd(self):
        if self.protected == False:
            return None
        return (
            self._media.get("files", {}).get("drm", {}).get("manifest", {}).get("dash")
        )

    @property
    def policy(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Policy")
        )

    @property
    def keypair(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Key-Pair-Id")
        )

    @property
    def signature(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Signature")
        )

    @property
    def mpdout(self):
        if not self.mpd:
            return None

    @property
    def file_text(self):
        text = self.get_text()
        text = self.file_cleanup(text, mediatype=self.mediatype)
        text = self.text_trunicate(text)
        return text

    @property
    def count(self):
        return self._count + 1

    # og filename
    @property
    def filename(self):
        if not self.url and not self.mpd:
            return None
        elif not self.responsetype == "Profile":
            return re.sub(
                "\.mpd$",
                "",
                (self.url or self.mpd)
                .split(".")[-2]
                .split("/")[-1]
                .strip("/,.;!_-@#$%^&*()+\\ "),
            )
        else:
            filename = re.sub(
                "\.mpd$",
                "",
                (self.url or self.mpd)
                .split(".")[-2]
                .split("/")[-1]
                .strip("/,.;!_-@#$%^&*()+\\ "),
            )
            return f"{filename}_{arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))}"

    @property
    async def final_filename(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z0-9]+$", f"", filename)
            filename = f"{filename}_{await self.selected_quality_placeholder}"
        # cleanup
        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(
                " ", data.get_spacereplacer(mediatype=self.mediatype), filename
            )

        except Exception as E:
            print(E)
        return filename

    @property
    def no_quality_final_filename(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z]+", f"", filename)
        # cleanup
        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(
                " ", data.get_spacereplacer(mediatype=self.mediatype), filename
            )
        except Exception as E:
            print(E)
        return filename

    @property
    def preview(self):
        if self.post.preview:
            return 1
        else:
            return 0

    @property
    def linked(self):
        return None

    @property
    def media(self):
        return self._media

    @property
    async def parse_mpd(self):
        if self._cached_parse_mpd:
            return self._cached_parse_mpd
        if not self.mpd:
            return
        params = {
            "Policy": self.policy,
            "Key-Pair-Id": self.keypair,
            "Signature": self.signature,
        }
        async with sessionManager.sessionManager(
            retries=constants.getattr("MPD_NUM_TRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
            semaphore=semaphore,
        ) as c:
            async with c.requests_async(url=self.mpd, params=params) as r:
                self._cached_parse_mpd = MPEGDASHParser.parse(await r.text_())
                return self._cached_parse_mpd

    @property
    async def mpd_dict(self):
        if not self.mpd:
            return
        mpd = await self.parse_mpd
        video = await self.mpd_video_helper(mpd=mpd)
        audio = await self.mpd_audio_helper(mpd=mpd)
        return audio, video

    @property
    def license(self):
        if not self.mpd:
            return None
        responsetype = self.post.post["responseType"]
        if responsetype in ["timeline", "archived", "pinned", "posts"]:
            responsetype = "post"
        return constants.getattr("LICENCE_URL").format(
            self.id, responsetype, self.postid
        )

    @property
    def mass(self):
        return self._post.mass

    @mediatype.setter
    def mediatype(self, val):
        self._media["type"] = val

    @property
    async def selected_quality(self):
        if self.protected == False:
            return self.normal_quality_helper()
        return await self.alt_quality_helper()

    @property
    async def selected_quality_placeholder(self):
        return await self.selected_quality or constants.getattr(
            "QUALITY_UNKNOWN_DEFAULT"
        )

    @property
    def protected(self):
        if self.mediatype not in {"videos", "texts"}:
            return False
        elif bool(self.media_source.get("source")):
            return False
        elif bool(self.files_source):
            return False
        return True

    # for use in dynamic names
    @property
    def needs_count(self):
        if set(["text", "postid", "post_id"]).isdisjoint(
            [
                name
                for text, name, spec, conv in list(
                    string.Formatter().parse(data.get_fileformat())
                )
            ]
        ):
            return False
        elif len(self._post.post_media) > 1 or self.responsetype in [
            "stories",
            "highlights",
        ]:
            return True
        return False

    @property
    def username(self):
        return self._post.username

    @property
    def model_id(self):
        return self._post.model_id

    @property
    def duration_string(self):
        return dates.format_seconds(self.duration) if self.duration else None

    def get_text(self):
        if self.responsetype != "Profile":
            text = (
                self._post.file_sanitized_text
                or self.filename
                or arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))
            )
        elif self.responsetype == "Profile":
            text = f"{arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))} {self.text or self.filename}"
        return text

    async def mpd_video_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd
        if not mpd:
            return
        allowed = quality.get_allowed_qualities()
        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "video/mp4", period.adaptation_sets
            ):
                kId = None
                for prot in adapt_set.content_protections:
                    if prot.value == None:
                        kId = prot.pssh[0].pssh
                        break

                selected_quality = None
                for ele in ["240", "720"]:
                    if ele not in allowed:
                        continue
                    selected_quality = selected_quality or next(
                        filter(
                            lambda x: x.height == int(ele), adapt_set.representations
                        ),
                        None,
                    )
                selected_quality = selected_quality or max(
                    adapt_set.representations, key=lambda x: x.height
                )
                for repr in adapt_set.representations:
                    if repr.height == selected_quality.height:
                        origname = f"{repr.base_urls[0].base_url_value}"
                        return {
                            "origname": origname,
                            "pssh": kId,
                            "type": "video",
                            "name": f"tempvid_{origname}",
                        }

    async def mpd_audio_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd
        if not mpd:
            return
        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "audio/mp4", period.adaptation_sets
            ):
                kId = None
                for prot in adapt_set.content_protections:
                    if prot.value == None:
                        kId = prot.pssh[0].pssh
                        log_helpers.updateSenstiveDict(kId, "pssh_code")
                        break
                for repr in adapt_set.representations:
                    origname = f"{repr.base_urls[0].base_url_value}"
                    return {
                        "origname": origname,
                        "pssh": kId,
                        "type": "audio",
                        "name": f"tempaudio_{origname}",
                    }

    def normal_quality_helper(self):
        allowed = quality.get_allowed_qualities()
        if self.mediatype != "videos":
            return "source"
        for ele in ["240", "720"]:
            if ele not in allowed:
                continue
            elif self._media.get("videoSources", {}).get(ele):
                return ele
        return "source"

    async def alt_quality_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd

        if not mpd:
            return
        allowed = quality.get_allowed_qualities()
        selected = None
        val = None

        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "video/mp4", period.adaptation_sets
            ):
                kId = None
                for ele in ["240", "720"]:
                    if ele not in allowed:
                        continue
                    selected = selected or next(
                        filter(
                            lambda x: x.height == int(ele), adapt_set.representations
                        ),
                        None,
                    )
                return str(selected.height) if selected else "source"

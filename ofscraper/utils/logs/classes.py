import copy
import logging
import re

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates_manager
import ofscraper.utils.logs.helpers as helpers


class PipeHandler(logging.Handler):
    """
    This handler sends events to a queue. Typically, it would be used together
    with a multiprocessing Queue to centralise logging to file in one process
    (in a multi-process application), so as to avoid file write contention
    between processes.

    This code is new in Python 3.2, but this class can be copy pasted into
    user code for use with earlier Python versions.
    """

    def __init__(self, pipe):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.pipe = pipe

    def prepare(self, record):
        """
        Prepare a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message and
        arguments, and removes unpickleable items from the record in-place.
        Specifically, it overwrites the record's `msg` and
        `message` attributes with the merged message (obtained by
        calling the handler's `format` method), and sets the `args`,
        `exc_info` and `exc_text` attributes to None.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.
        """
        # The format operation gets traceback text into record.exc_text
        # (if there's exception data), and also returns the formatted
        # message. We can then use this to replace the original
        # msg + args, as these might be unpickleable. We also zap the
        # exc_info, exc_text and stack_info attributes, as they are no longer
        # needed and, if not None, will typically not be pickleable.
        msg = self.format(record)
        # bpo-35726: make copy of record to avoid affecting other handlers in the chain.
        record = copy.copy(record)
        record.message = msg
        record.msg = msg
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return record

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        try:
            msg = self.prepare(record)
            self.pipe[0].send(msg)
        except Exception:
            self.handleError(record)


class DebugOnly(logging.Filter):
    def filter(self, record):
        if record.levelno == 10 or record.levelno == 11:
            return True
        return False


class TraceOnly(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return True
        return False


class TraceBackOnly(logging.Filter):
    def filter(self, record):
        if record.levelno == 11:
            return True
        return False


class NoTraceBack(logging.Filter):
    def filter(self, record):
        if record.levelno != 11:
            return True
        return False


class NoDebug(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return False
        return True


class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.sess = sessionManager.sessionManager(
            backend="httpx",
            total_timeout=10,
            retries=constants.getattr("DISCORD_NUM_TRIES"),
            wait_min=constants.getattr("DISCORD_MIN_WAIT"),
            wait_max=constants.getattr("DISCORD_MAX_WAIT"),
        )
        self._thread = None
        self._baseurl = data.get_discord()
        self._url = self._baseurl
        self._appendhelper()

    def _appendhelper(self, date=None):
        if constants.getattr("DISCORD_THREAD_OVERRIDE"):
            with self.sess as sess:
                try:
                    with sess.requests(
                        "{url}?wait=true".format(url=self._baseurl),
                        "post",
                        headers={"Content-type": "application/json"},
                        json={
                            "thread_name": date
                            or dates_manager.getLogDate().get("now"),
                            "content": date or dates_manager.getLogDate().get("now"),
                        },
                    ) as _:
                        pass
                except Exception as E:
                    None

    def emit(self, record):
        if isinstance(record, str):
            self._url = record
            return

        def inner(sess):
            with sess:
                try:
                    with sess.requests(
                        self._url,
                        "post",
                        cookies=False,
                        sign=False,
                        headers={"Content-type": "application/json"},
                        json={
                            "content": log_entry,
                            "thread_name": self._thread,
                        },
                    ) as r:
                        if not r.status == 204:
                            raise Exception
                except Exception:
                    None

        log_entry = self.format(record)
        url = data.get_discord()
        log_entry = re.sub("\[bold\]|\[/bold\]", "**", log_entry)
        log_entry = f"{log_entry}\n\n"
        if url == None or url == "":
            return

        inner(self.sess)


class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._widget = None

    def emit(self, record):
        # only emit after widget is set
        if self._widget == None:
            return
        log_entry = self.format(record)
        log_entry = f"{log_entry}"
        self._widget.write(log_entry)

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        self._widget = widget


class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        s = re.sub("&Policy=[^&\"']+", "&Policy={hidden}", s)
        s = re.sub("&Signature=[^&\"']+", "&Signature={hidden}", s)
        s = re.sub("&Key-Pair-Id=[^&\"']+", "&Key-Pair-Id={hidden}", s)
        for ele in helpers.getSenstiveDict().items():
            s = re.sub(re.escape(str(ele[0])), str(ele[1]), s)
        return s

    def format(self, record):
        original = logging.Formatter.format(self, record)  # call parent method
        return self._filter(original)


class LogFileFormatter(SensitiveFormatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        s = SensitiveFormatter._filter(s)
        s = re.sub("\[bold\]|\[/bold\]", "", s)
        return s

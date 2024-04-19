import multiprocessing
from threading import Event

import ofscraper.utils.manager as manager_

queue_ = None
otherqueue_ = None
otherqueue2_ = None
main_event = None
other_event = None
main_log_thread = None
other_log_thread = None


def init_values():
    global queue_
    global otherqueue_
    global main_event
    global other_event
    queue_ = multiprocessing.Queue()
    otherqueue_ = manager_.get_manager().Queue()
    main_event = Event()
    other_event = Event()

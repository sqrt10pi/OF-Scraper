#!/root/OF-Scraper/.venv/bin/python
import multiprocessing
import sys
import ofscraper.start as start

def main():
    start.set_mulitproc_start_type()    
    start.logger.init_queues()
    start.set_eventloop()
    start.startvalues()
    start.discord_warning()
    start.main()

if __name__ == '__main__': 
    multiprocessing.freeze_support()

    main()


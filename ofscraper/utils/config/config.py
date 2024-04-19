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

from humanfriendly import parse_size

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.binaries as binaries
import ofscraper.utils.config.context as config_context
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_

console = console_.get_shared_console()
log = logging.getLogger("shared")


def read_config(update=True):
    while True:
        with config_context.config_context():
            config = config_file.open_config()
            if update and schema.config_diff(config):
                config = config_file.auto_update_config(config)
            if config.get("config"):
                config = config["config"]
            return config


def update_config(field: str, value):
    config = config_file.open_config()
    if config.get("config"):
        config = config["config"]
    config.update({field: value})
    new_config = schema.get_current_config_schema(config)
    config_file.write_config(new_config)
    log.debug(f"new config: {config}")
    return new_config


def update_config_full(config, updated_config):
    if config.get("config"):
        config = config["config"]
    if updated_config.get("config"):
        updated_config = updated_config["config"]
    config.update(updated_config)
    log.debug(f"new config: {config}")
    config_file.write_config(config)
    return config


def update_mp4decrypt():
    config = {"config": read_config()}
    if prompts.auto_download_mp4_decrypt() == "Yes":
        config["config"]["mp4decrypt"] = binaries.mp4decrypt_download()
    else:
        config["config"]["mp4decrypt"] = prompts.mp4_prompt()
    config_file.write_config(config)


def update_ffmpeg():
    config = {"config": read_config()}
    if prompts.auto_download_ffmpeg() == "Yes":
        config["config"]["ffmpeg"] = binaries.ffmpeg_download()
    else:
        config["config"]["ffmpeg"] = prompts.ffmpeg_prompt()
    config_file.write_config(config)

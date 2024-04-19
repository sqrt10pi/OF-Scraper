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

import contextlib
import logging
import pathlib
import sqlite3

from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations_.wrapper as wrapper

console = Console()
log = logging.getLogger("shared")

# user_id==modes.id cause of legacy
profilesCreate = """
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL,
	PRIMARY KEY (id)
)
"""
modelsCreate = """
CREATE TABLE IF NOT EXISTS models (
	id INTEGER NOT NULL,
	model_id INTEGER NOT NULL,
	UNIQUE (model_id)
	PRIMARY KEY (id)
)
"""
userNameList = """
SELECT username FROM profiles where user_id=(?)
"""

profileTableCheck = """
SELECT name FROM sqlite_master WHERE type='table' AND name='profiles';
"""
profileInsert = """
INSERT INTO 'profiles' (user_id, username)
SELECT ?, ?
WHERE NOT EXISTS (
  SELECT 1 FROM 'profiles'
  WHERE user_id = ? AND username = ?
);
"""


profileInsertTransition = """INSERT INTO 'profiles'(
user_id,username)
            VALUES (?, ?);
"""
modelInsert = """
INSERT INTO models (model_id)
SELECT ?
WHERE NOT EXISTS (
  SELECT 1 FROM models WHERE model_id = ?
);
"""
profilesALL = """
select user_id,username from profiles
"""
profilesDrop = """
DROP TABLE profiles;
"""


profileUnique = """
SELECT DISTINCT user_id FROM profiles
"""


@wrapper.operation_wrapper_async
def get_profile_info(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(userNameList, ([model_id]))
            return (list(map(lambda x: x[0], cur.fetchall())) or [None])[0]
        except sqlite3.OperationalError:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper_async
def create_profile_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(profilesCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def write_profile_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [model_id, username, model_id, username]
        cur.execute(profileInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_profile_table_transition(insertData, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(profileInsertTransition, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def check_profile_table_exists(model_id=None, username=None, conn=None):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return False
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(profileTableCheck).fetchall()) > 0:
            return True
        return False


@wrapper.operation_wrapper_async
def get_all_profiles(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profiles = cur.execute(profilesALL).fetchall()
            conn.commit()
            return profiles
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper_async
def drop_profiles_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(profilesDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def create_models_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(modelsCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def write_models_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(modelInsert, [model_id, model_id])
        conn.commit()


@wrapper.operation_wrapper
def get_single_model(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        models_ids = [
            dict(row)["user_id"] for row in cur.execute(profileUnique).fetchall()
        ]
        return models_ids[0] if len(models_ids) == 1 else None


async def remove_unique_constriant_profile(model_id=None, username=None):
    data = await get_all_profiles(model_id=model_id, username=username)
    await drop_profiles_table(model_id=model_id, username=username)
    await create_profile_table(model_id=model_id, username=username)
    await write_profile_table_transition(data, model_id=model_id, username=username)

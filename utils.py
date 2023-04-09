import os
import logging
from logging.handlers import RotatingFileHandler
import sqlalchemy
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy_utils import database_exists, create_database
from typing import Tuple
import pandas as pd

def create_logger(file_name: str) -> logging.Logger:
    log_path = os.path.join(os.path.dirname(file_name), "logs")
    log_name = os.path.basename(file_name[:-3])
    log_filename = os.path.join(log_path, log_name + ".log")

    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    rotating_handler = RotatingFileHandler(filename=log_filename, mode='a',
                                           maxBytes=5 * 1024 * 1024, backupCount=10, encoding=None, delay=False)
    rotating_handler.setFormatter(log_formatter)
    rotating_handler.setLevel(level=logging.INFO)

    logger = logging.getLogger(log_name)
    logger.setLevel(level=logging.INFO)
    logger.addHandler(rotating_handler)
    logger.addHandler(logging.StreamHandler())

    logger.info("-- LOGGER LOADED --")
    return logger


def create_database_session() -> Tuple[Session,  sqlalchemy.engine.Engine]:
    db_name = os.environ.get('CREMAET_DATABASE')
    if os.environ.get('CREMAET_DEBUG', 'true').lower() == 'true':
        db_name = os.environ['CREMAET_TEST_DATABASE']

    connection_str = (f"mysql+pymysql://{os.environ['CREMAET_DB_USER']}:"
                      f"{os.environ['CREMAET_DB_PASSWORD']}@{os.environ['CREMAET_DB_HOST']}:"
                      f"{os.environ['CREMAET_DB_PORT']}/{db_name}")

    # Define the MariaDB engine using MariaDB Connector/Python
    engine = sqlalchemy.create_engine(connection_str)

    if not database_exists(engine.url):
        create_database(engine.url)

    session_maker = sessionmaker()
    session_maker.configure(bind=engine)
    session = session_maker()
    session.commit()
    return session, engine


def load_dialogs() -> dict:
    dialogs = dict()
    # An optimization - don't require pandas
    df = pd.reac_csv('dialogs.csv', sep=';')
    for row in df.itertuples():
        dialogs[row.key] = row.value
    return dialogs

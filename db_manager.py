from datetime import datetime
from typing import Optional, Type, List

import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query
from sqlalchemy_utils import database_exists, drop_database

from db_tables import Base
from db_tables import User, Participant, Event, StatusEnum
from utils import create_logger, create_database_session


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DBManager(metaclass=Singleton):

    def __init__(self):
        session, engine = create_database_session()
        self.session = session
        self.engine = engine
        self.logger = create_logger(__file__)

        Base.metadata.create_all(self.engine)

    def clean_tables(self) -> None:
        self.session.query(User).delete()
        self.session.query(Event).delete()
        self.session.query(Participant).delete()
        self.session.commit()

    def __delete_database(self) -> None:
        if database_exists(self.engine.url):
            drop_database(self.engine.url)

    def reconnect(self):
        # This method exectutes when there is a fatal error with the database
        # is the same steps as __init__
        # TODO - find the best way to perform this without warnings
        session, engine = create_database_session()
        self.session = session
        self.engine = engine

    ########
    #
    # USER METHODS
    #
    ########
    def add_user(self, telegram_id, first_name, last_name=None, is_admin=False) -> Optional[User]:
        try:
            new_user = User(telegram_id=telegram_id, first_name=first_name,
                            last_name=last_name, is_admin=is_admin)
            self.session.add(new_user)
            self.session.commit()
            return new_user
        except IntegrityError as ie:
            self.logger.error(ie)
            return None
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        try:
            user = self.session.query(User).filter_by(telegram_id=telegram_id).one_or_none()
            return user
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def get_all_users(self) -> list[Type[User]]:
        return self.session.query(User).all()

    def change_user_status(self, user: User, status: StatusEnum) -> bool:
        try:
            self.session.query(User).filter_by(user_id=user.user_id).update({'status': status})
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return False

    def promote_to_admin(self, user: User):
        try:
            user.is_admin = True
            self.session.commit()
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return False

    def add_participant(self, display_name: str, join_date: datetime.date) -> Optional[Participant]:
        try:
            new_participant = Participant(display_name=display_name, join_date=join_date)
            self.session.add(new_participant)
            self.session.commit()
            return new_participant
        except IntegrityError as ie:
            self.logger.error(ie)
            return None
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def delete_participant_by_id(self, participant: Participant) -> bool:
        try:
            self.session.query(Participant).filter_by(participant=participant.participant_id).one().delete()
            return True
        # Important - since the id is the pk, no multiple results can be found therefore
        # sqlalchemy.orm.exc.MultipleResultsFound is impossible to trigger
        except sqlalchemy.exc.NoResultFound as nrfe:
            self.logger.error(nrfe)
            return False
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return False

    def get_participant_by_id(self, participant_id: int) -> Optional[Participant]:
        try:
            participant = self.session.query(Participant).filter_by(participant_id=participant_id).one_or_none()
            return participant
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def get_participant_by_display_name(self, display_name) -> Optional[Participant]:
        try:
            participant = self.session.query(Participant).filter_by(display_name=display_name).one_or_none()
            return participant
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def get_all_participants(self) -> list[Participant]:
        return self.session.query(Participant).all()

    def add_event(self, participant: Participant, date: datetime.date) -> Optional[Event]:
        try:
            event = Event(participant=participant.participant_id, date=date)
            self.session.add(event)
            self.session.commit()
            return event
        except IntegrityError as ie:
            self.logger.error(ie)
            return None
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return None

    def delete_event(self, event: Event) -> bool:
        try:
            self.session.query(Event).filter_by(event_id=event.event_id).delete()
            return True
        except IntegrityError as ie:
            self.logger.error(ie)
            return False
        except Exception as e:
            self.logger.error(e)
            self.reconnect()
            return False

    def get_all_events(self) -> list[Type[Event]]:
        return self.session.query(Event).order_by(Event.date.desc()).all()

    def get_events_by_participant(self, participant: Participant) -> list[Type[Event]]:
        return self.session.query(Event).filter_by(participant=participant.participant_id).all()

    def get_events_between_dates(self, starting: datetime.date, ending: datetime.date) -> list[Type[Event]]:
        return self.session.query(Event).filter(Event.date.between(starting, ending)).all()

    def get_last_n_events(self, limit_rows: int) -> list[Type[Event]]:
        return self.session.query(Event).order_by(Event.date.desc()).limit(limit_rows).all()











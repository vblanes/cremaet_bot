import sqlalchemy
from sqlalchemy import ForeignKey, Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = 'User'
    user_id = Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
    first_name = Column(sqlalchemy.String(length=32))
    last_name = Column(sqlalchemy.String(length=64))
    telegram_id = Column(sqlalchemy.BigInteger, unique=True)
    is_admin = Column(sqlalchemy.Boolean, default=False)


class Participant(Base):
    __tablename__ = 'Participant'
    participant_id = Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
    display_name = Column(sqlalchemy.String(length=64), unique=True)
    join_date = Column(sqlalchemy.DateTime, server_default=func.now())


class Event(Base):
    __tablename__ = 'Event'
    event_id = Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
    participant = Column(sqlalchemy.Integer, ForeignKey(Participant.participant_id))
    date = join_date = Column(sqlalchemy.DateTime, server_default=func.now(), unique=True)

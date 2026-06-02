"""SQLAlchemy declarative base. All models inherit from `Base`."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

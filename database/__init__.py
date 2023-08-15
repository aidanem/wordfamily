# -*- coding: utf-8 -*-

import logging
import os

import sqlalchemy as sqla
import sqlalchemy.orm
from sqlalchemy.ext.declarative import declarative_base

import hermes


DeclarativeGroup = declarative_base()

def default_engine():
    return hermes.SQLiteEngine(
        path = os.path.join("glyphs.db"),
        foreign_keys = True,
    )

def default_session():
    return default_engine().Session()
    

from .declaration import *



# -*- coding: utf-8 -*-

import logging
import os

from sqlalchemy.ext.declarative import declarative_base

import hermes

module_path = os.path.abspath(os.path.dirname(__file__))

DeclarativeGroup = declarative_base()

def default_engine():
    return hermes.SQLiteEngine(
        path = os.path.join(module_path, "words.db"),
        foreign_keys = True,
    )

def default_session():
    return default_engine().Session()

from .glyph import *
from .word_family import *
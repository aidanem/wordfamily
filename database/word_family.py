# -*- coding: utf-8 -*-

import logging
import re

import sqlalchemy as sqla
import sqlalchemy.orm

import hermes

from .declaration import DeclarativeGroup, default_engine, default_session
from .glyph import Script



class Language(DeclarativeGroup, hermes.DynamicReprMixin, hermes.MergeMixin):
    __tablename__ = 'languages'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String, unique=True)
    iso639 = sqla.Column(sqla.String)
    
    _unique_keys = [
        "name",
    ]
    
    def safe_name(self):
        return re.sub(r'\W', '', self.name)
    
    @classmethod
    def get_by_name(cls, name, session):
        try:
            language = session.query(
                    cls
                ).filter(
                    cls.name == name,
                ).one()
        except sqlalchemy.orm.exc.NoResultFound:
            try:
                language = LanguageAutoCorrection.get_language_by_input(name, session)
            except:
                raise ValueError(f"No language found for input: {name!r}")
        return language
    
    def script_from_iso639(self, session):
        if self.iso639 is not None:
            for tag_part in self.iso639.split("-")[1:]:
                try:
                    return Script.get_by_iso_15924(tag_part, session)
                except ValueError:
                    continue
            else:
                return None
    
    children = sqlalchemy.orm.relationship(
        "Language",
        secondary = "language_descent_mapping",
        back_populates = "parents",
        primaryjoin = "Language.id == LanguageDescentMapping.parent_id",
        secondaryjoin = "LanguageDescentMapping.child_id == Language.id",
    )
    
    parents = sqlalchemy.orm.relationship(
        "Language",
        secondary = "language_descent_mapping",
        back_populates = "children",
        primaryjoin = "Language.id == LanguageDescentMapping.child_id",
        secondaryjoin = "LanguageDescentMapping.parent_id == Language.id",
    )
    
    styles = sqlalchemy.orm.relationship(
        "LanguageStyle",
        secondary = "language_style_mapping",
        primaryjoin = "Language.id == LanguageStyleMapping.language_id",
        secondaryjoin = "LanguageStyleMapping.style_id == LanguageStyle.id",
    )

class LanguageStyle(DeclarativeGroup, hermes.DynamicReprMixin, hermes.MergeMixin):
    __tablename__ = 'language_styles'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String, unique=True)
    dot_styling = sqla.Column(sqla.String, unique=True)
    
    _unique_keys = [
        "name",
    ]


class LanguageStyleMapping(
        DeclarativeGroup,
        hermes.DynamicReprMixin,
        hermes.MergeMixin
    ):
    __tablename__ = 'language_style_mapping'
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'language_id',
            'style_id',
        ),
    )
    
    language_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("languages.id"),
    )
    style_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("language_styles.id"),
    )
    
    _unique_keys = [
        "language_id",
        "style_id",
    ]


class LanguageDescentMapping(
        DeclarativeGroup,
        hermes.DynamicReprMixin,
        hermes.MergeMixin
    ):
    __tablename__ = 'language_descent_mapping'
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'parent_id',
            'child_id',
        ),
    )
    
    parent_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("languages.id"),
    )
    child_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("languages.id"),
    )
    
    _unique_keys = [
        "parent_id",
        "child_id",
    ]

class LanguageAutoCorrection(
        DeclarativeGroup,
        hermes.DynamicReprMixin,
        hermes.MergeMixin
    ):
    __tablename__ = 'language_autocorrections'
    
    input = sqla.Column(sqla.String, primary_key=True)
    language_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("languages.id")
    )
    
    _unique_keys = ["input"]
    
    @classmethod
    def get_language_by_input(cls, input, session):
        language = session.query(
                cls
            ).filter(
                cls.input == input,
            ).one().language
        return language
    
    language = sqlalchemy.orm.relationship("Language")

class Word(DeclarativeGroup, hermes.DynamicReprMixin, hermes.MergeMixin):
    __tablename__ = 'words'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    language_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("languages.id")
    )
    orthography = sqla.Column(sqla.String)
    latin_transliteration = sqla.Column(sqla.String)
    meaning = sqla.Column(sqla.String)
    inline_note = sqla.Column(sqla.String)
    footnote_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("footnotes.id")
    )
    
    _unique_keys = [
        "language_id",
        "orthography",
        "latin_transliteration",
    ]
    
    language = sqlalchemy.orm.relationship("Language")
    
    children = sqlalchemy.orm.relationship(
        "Word",
        secondary = "word_derivations",
        back_populates = "parents",
        primaryjoin = "Word.id == Derivation.parent_id",
        secondaryjoin = "Derivation.child_id == Word.id",
    )
    
    parents = sqlalchemy.orm.relationship(
        "Word",
        secondary = "word_derivations",
        back_populates = "children",
        primaryjoin = "Word.id == Derivation.child_id",
        secondaryjoin = "Derivation.parent_id == Word.id",
    )
    footnote = sqlalchemy.orm.relationship("Footnote")
    
    tags = sqlalchemy.orm.relationship(
        "WordTag",
        secondary = "tag_mapping",
        back_populates = "words",
        primaryjoin = "Word.id == WordTagMapping.word_id",
        secondaryjoin = "WordTagMapping.tag_id == WordTag.id",
    )



class WordTag(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'word_tags'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    text = sqla.Column(sqla.String, unique=True)
    
    words = sqlalchemy.orm.relationship(
        "Word",
        secondary = "tag_mapping",
        back_populates = "tags",
        primaryjoin = "WordTag.id == WordTagMapping.tag_id",
        secondaryjoin = "WordTagMapping.word_id == Word.id",
    )

class WordTagMapping(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'tag_mapping'
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'word_id',
            'tag_id',
        ),
    )
    
    word_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("words.id"),
    )
    tag_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("word_tags.id"),
    )

class Footnote(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'footnotes'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    text = sqla.Column(sqla.String)

class DerivationType(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'word_derivation_types'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String, unique=True)


class Derivation(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'word_derivations'
    
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'parent_id',
            'child_id',
        ),
    )
    parent_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("words.id")
    )
    child_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("words.id")
    )
    confident = sqla.Column(sqla.Boolean, default=True)
    derivation_type_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("word_derivation_types.id")
    )
    footnote_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("footnotes.id")
    )
    
    derivation_type = sqlalchemy.orm.relationship("DerivationType")
    footnote = sqlalchemy.orm.relationship("Footnote")


def write_language_json():
    import json
    from collections import defaultdict
    session = default_session()
    language_autocorrects = session.query(LanguageAutoCorrection).all()
    autocorrects_map = defaultdict(list)
    
    for autocorrection in language_autocorrects:
        autocorrects_map[autocorrection.language_id].append(autocorrection.input)
    
    languages = session.query(Language).all()
    language_data = []
    for language in languages:
        lang_dict = {
            "name": language.name,
            "subtag": language.subtag,
            "style_classes": list(language.style_classes),
            "direct_parents": [parent.name for parent in language.parents],
            "autocorrects": autocorrects_map[id],
        }
        language_data.append(lang_dict)
    
    
    with open("languages.json", "w") as json_file:
        json.dump(language_data, json_file, indent=2)

def read_language_json(initialize=False):
    import json
    with open("languages.json", "r") as json_file:
        language_data = json.load(json_file)
    if initialize:
        default_engine().initialize_tables(
            DeclarativeGroup.metadata,
            re_initialize = True,
        )
    session = default_session()
    if initialize:
        session.add_all([
            DerivationType(name = "synchronic_derivation"),
            DerivationType(name = "diachronic_derivation"),
            DerivationType(name = "borrowing"),
        ])
    for lang_dict in language_data:
        language_obj = Language(
            name = lang_dict["name"],
            iso639 = lang_dict["subtag"],
            style_classes = []
        )
        hermes.prompt_merge(Language, language_obj, session, "name")
    session.commit()
    for lang_dict in language_data:
        language = Language.get_by_name(lang_dict["name"], session)
        style_classes = set(language.style_classes).union(lang_dict["style_classes"])
        if lang_dict["direct_parents"]:
            for parent_language_name in lang_dict["direct_parents"]:
                parent = Language.get_by_name(parent_language_name, session)
                language_descent_obj = LanguageDescentMapping(
                    parent_id = parent.id,
                    child_id = language.id,
                )
                hermes.prompt_merge(Language, language_obj, session, "name")
                style_classes = style_classes.union(parent.style_classes)
                language.style_classes = list(style_classes)
                session.merge(language_descent_obj)
        if lang_dict["autocorrects"]:
            for input in lang_dict["autocorrects"]:
                autocorrect_obj = LanguageAutoCorrection(
                    language.id,
                    input,
                )
                session.merge(autocorrect_obj)
    session.commit()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '-r', '--reinitialize',
        action = 'store_true',
    )
    
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-8s [%(name)s] [%(threadName)s] %(message)s")
    
    read_language_json(initialize=args.reinitialize)
    
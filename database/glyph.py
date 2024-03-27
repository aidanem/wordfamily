# -*- coding: utf-8 -*-

import logging
import re

import sqlalchemy as sqla
import sqlalchemy.orm

import hermes


from .declaration import DeclarativeGroup


iso_15924_pattern = re.compile("[A-Z][a-z]{3}")


class Script(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'scripts'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String)
    adjective = sqla.Column(sqla.String)
    iso_15924 = sqla.Column(sqla.String)
    #type_ = sqla.Column(sqla.String) # switch to multiple types per Script
    direction = sqla.Column(sqla.String)
    noto_fontname = sqla.Column(sqla.String)
    comment = sqla.Column(sqla.String)
    
    glyphs = sqlalchemy.orm.relationship("Glyph", back_populates='script')

    alternate_names = sqlalchemy.orm.relationship(
        "ScriptAlternateNames",
        back_populates='script'
    )

    ordering_sequences = sqlalchemy.orm.relationship(
        "OrderingSequence",
        back_populates='script'
    )

    transliteration_schemes = sqlalchemy.orm.relationship(
        "TransliterationScheme",
        back_populates='source_script',
        primaryjoin = "Script.id == TransliterationScheme.source_script_id",
    )
    
    @classmethod
    def get_by_iso_15924(cls, input, session):
        # get any script entry which matches iso15924
        if iso_15924_pattern.match(input) is not None:
            try:
                script = session.query(
                        cls
                    ).filter(
                        cls.iso_15924 == input,
                    ).first()
                return script
            except sqlalchemy.orm.exc.NoResultFound:
                raise ValueError(f"{input!r} was not found in the script tags.")
        else:
            raise ValueError(f"{input!r} is not a valid ISO 15924 script tag.")
    
    # generate css file
    
    static_preface = """/* */
span.orthography {
    font-family: "Noto Sans", "Noto Sans UI";
}
span.orthography {font-style: normal;}
span.orthography:not([lang]) {font-style: italic;}
span.orthography[lang$="-Latn"] {font-style: italic;}
"""
    block_template = """
/* {0.name} */
span.orthography[lang*="-{0.iso_15924}"] {{
    font-family: '{0.noto_fontname}';
}}
""".format
    
    
    @classmethod
    def export_css_file(cls, session, outfilename="orthography.css"):
        
        with open(outfilename, 'w', encoding = "utf-8",) as outfile:
            outfile.write(cls.static_preface)
            all_scripts = session.query(cls)
            for script in all_scripts:
                outfile.write(cls.block_template(script))


class ScriptAlternateNames(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'script_alternate_names'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    script_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("scripts.id")
    )
    name = sqla.Column(sqla.String)
    
    script = sqlalchemy.orm.relationship(
        "Script",
        back_populates='alternate_names',
    )


class OrderingSequence(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'ordering_sequences'
    __table_args__ = (
        sqla.UniqueConstraint(
            'script_id',
            'priority',
        ),
        sqla.UniqueConstraint(
            'script_id',
            'name',
        ),
    )
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    script_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("scripts.id")
    )
    name = sqla.Column(sqla.String)
    priority = sqla.Column(sqla.Integer)
    
    script = sqlalchemy.orm.relationship("Script", back_populates='ordering_sequences')
    
    mappings = sqlalchemy.orm.relationship("OrderMapping", back_populates='sequence')
    
    def order(self, glyphs):
        glyph_map = {glyph.id: glyph for glyph in glyphs}
        ordered_glyphs = {mapping.order: glyph_map[mapping.glyph_id] for mapping in self.mappings}
        unordered_glyphs = [glyph for glyph in glyphs if glyph not in ordered_glyphs.values()]
        return ordered_glyphs, unordered_glyphs
    


class TransliterationScheme(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'transliteration_schemes'
    __table_args__ = (
        sqla.UniqueConstraint(
            'source_script_id',
            'priority',
        ),
    )
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    source_script_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("scripts.id")
    )
    target_script_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("scripts.id")
    )
    name = sqla.Column(sqla.String)
    priority = sqla.Column(sqla.Integer)
    
    source_script = sqlalchemy.orm.relationship(
        "Script",
        back_populates='transliteration_schemes',
        primaryjoin = "Script.id == TransliterationScheme.source_script_id",
    )
    
    target_script = sqlalchemy.orm.relationship(
        "Script",
        primaryjoin = "Script.id == TransliterationScheme.target_script_id",
    )
    
    mappings = sqlalchemy.orm.relationship("TransliterationMapping", back_populates='scheme')
    

class Glyph(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'glyphs'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    script_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("scripts.id", ondelete='SET NULL')
    )
    diacritic = sqla.Column(sqla.Boolean, default=False)
    
    unicode_ = sqla.Column(sqla.Unicode, unique=True, index=True)
    
    name = sqla.Column(sqla.String)
    name_meaning = sqla.Column(sqla.String)
    english_name = sqla.Column(sqla.String)
    
    def __str___(self):
        return self.unicode_
    
    # make additional relations that get descent mapping,
    # instead of skipping directly to the related glyph (get confidence)
    children = sqlalchemy.orm.relationship(
        "Glyph",
        secondary = "glyph_descent_mapping",
        back_populates = "parents",
        primaryjoin = "Glyph.id == GlyphDescentMapping.parent_id",
        secondaryjoin = "GlyphDescentMapping.child_id == Glyph.id",
    )
    
    parents = sqlalchemy.orm.relationship(
        "Glyph",
        secondary = "glyph_descent_mapping",
        back_populates = "children",
        primaryjoin = "Glyph.id == GlyphDescentMapping.child_id",
        secondaryjoin = "GlyphDescentMapping.parent_id == Glyph.id",
    )
    
    script = sqlalchemy.orm.relationship(
        "Script",
        back_populates='glyphs',
    )
    variants = sqlalchemy.orm.relationship(
        "GlyphVariant",
        back_populates='primary',
    )
    orderings = sqlalchemy.orm.relationship(
        "OrderMapping",
        back_populates='glyph',
    )
    
    def unicode_display(self):
        """if self.diacritic:
            return "\u25cc"+self.unicode_ #diacritic carrier, not working
        else:"""
        return self.unicode_
    
    def header_str(self, script=True):
        main_str = ""
        script_str = ""
        u_ = self.unicode_display()
        name_ = repr(self.english_name)
        if self.unicode_ and self.english_name:
            main_str = f'{u_} ({name_})'
        elif self.unicode_:
            main_str = u_
        elif self.english_name:
            main_str = name_
        else:
            main_str = f"unnamed glyph #{self.id}"
        if script:
            script_str = self.script.name + " "
        
        return self.script.name + " " + main_str
    
    def multiline_print(self, script=True, max_depth=2, indent=0):
        
        indent_str = " "*(indent*2)
        print(indent_str + self.header_str(script))
        if max_depth > 0:
            if self.parents:
                print(
                    "{i}from: ".format(
                        i = " "*(indent*2 + 1)
                    )
                )
                for parent_glyph in self.parents:
                    parent_glyph.multiline_print(
                        max_depth = max_depth - 1,
                        indent = indent + 1,
                    )
    
    def transliterate(self, scheme, session):
        import transliteration
        return transliteration.transliterate(self.unicode_, scheme, session)
    
    @classmethod
    def get_by_unicode_or_name(cls, glyph_identifier, session):
        try:
            return session.query(
                cls,
            ).filter(
                cls.unicode_ == glyph_identifier,
            ).one()
        except sqla.orm.exc.NoResultFound:
            try:
                return session.query(
                    cls,
                ).filter(
                    cls.name == glyph_identifier,
                ).one()
            except sqla.orm.exc.NoResultFound:
                return None

class GlyphVariant(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'glyph_variants'
    
    id = sqla.Column(sqla.Integer, primary_key=True)
    primary_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("glyphs.id"),
        index=True,
    )
    label = sqla.Column(sqla.String)
    unicode_ = sqla.Column(sqla.Unicode, unique=True, index=True)
    
    
    primary = sqlalchemy.orm.relationship("Glyph", back_populates='variants')

class OrderMapping(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'order_mappings'
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'sequence_id',
            'order',
        ),
    )
    
    sequence_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("ordering_sequences.id")
    )
    order = sqla.Column(sqla.Integer)
    glyph_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("glyphs.id")
    )
    
    sequence = sqlalchemy.orm.relationship(
        "OrderingSequence",
        back_populates='mappings',
    )
    
    glyph = sqlalchemy.orm.relationship("Glyph", back_populates='orderings')


class TransliterationMapping(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'transliteration_mapping'
    
    scheme_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("transliteration_schemes.id"),
        primary_key=True
    )
    source_unicode = sqla.Column(sqla.String, primary_key=True)
    target_unicode = sqla.Column(sqla.String)
    
    scheme = sqlalchemy.orm.relationship(
        "TransliterationScheme",
        back_populates='mappings',
    )


class GlyphDescentMapping(DeclarativeGroup, hermes.DynamicReprMixin):
    __tablename__ = 'glyph_descent_mapping'
    __table_args__ = (
        sqla.PrimaryKeyConstraint(
            'parent_id',
            'child_id',
        ),
    )
    
    parent_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("glyphs.id"),
    )
    child_id = sqla.Column(
        sqla.Integer,
        sqla.ForeignKey("glyphs.id"),
    )
    confidence = sqla.Column(sqla.Boolean, default=True)
    

sqla.Index(
    'child_parent_ix', #index primary keys in opposite order
    GlyphDescentMapping.child_id,
    GlyphDescentMapping.parent_id,
)



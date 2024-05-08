# coding: utf-8

from collections import OrderedDict, deque
import logging
import re

import language_database as db

markup_pattern = re.compile(r"^(?P<level>[-?]+>)?\s*(?P<language>[^`<>()#{}]+)(?P<orthography>\`[^`]+\`)?\s*(?P<transliteration><.+?>)?\s*(?P<transcription>\[.+?\])?(?P<uniquifier>»\d+)?(?P<teaser>!)?\s*(?P<meaning>: \".+?\")?\s*(?P<tags>{.+?})?\s*(?P<note>\(.+?\))?\s*(?P<footnote>[ ]*\#+)?")

def html_safe(text):
    if text:
        text = re.sub(r"<([^>]+)>", r"<span class='transliteration'>\1</span>", text)
        text = re.sub(r"\`(.+?)\`(=([\w-]+))*", r"<span class='orthography' lang='\3'>\1</span>", text)
        text = re.sub(r"\[([^\]\|]+)\|([^\]\|]+)]", r"<a href='\1'>\2</a>", text)
        text = re.sub(r"(http\S+)", r"<a href='\1'>\1</a>", text)
        text = re.sub(r"href='wff-(\w+)'", r"href='/word-family-\1.html'", text)
        return text

class Word(object):
    
    def __init__(self, language, _id, _db_id=None, orthography=None, transliteration=None, transcription=None, is_teaser=False, uniquifier=None, meaning=None, tags=set(), note=None, footnote_id=None):
        self.language = language
        self._id = _id
        self._db_id = _db_id
        self.orthography = orthography
        self.transliteration = transliteration
        self.transcription = transcription #not currently used
        self.is_teaser = is_teaser
        self.uniquifier = uniquifier
        self.meaning = meaning
        self.child_relations = []
        self.parent_relations = []
        self.derivation_paths = []
        self.tags = tags
        self.note = note
        self.footnote_id = footnote_id
        
    
    def __repr__(self):
        return f"{self.__class__.__name__}(language={self.language.name!r}, orthography={self.orthography!r}, transliteration={self.transliteration!r}, transcription={self.transcription!r}, meaning={self.meaning!r}, note={self.note!r})"
    
    def possible_match(self, other):
        if self.uniquifier is not None and other.uniquifier is not None:
            if self.uniquifier != other.uniquifier:
                return False
        language_match = False
        word_match = False
        if self.language == other.language:
            language_match = True
        elif self.language.id is None: #generic languages
            if other.language.id is None:
                language_match = self.language.name == other.language.name
                
        if self.orthography and other.orthography:
            word_match = self.orthography == other.orthography
        elif self.transliteration and other.transliteration:
            word_match = self.transliteration == other.transliteration
        return language_match and word_match
    
    @property
    def id(self):
        return "{lang}_{id}".format(
            lang = self.language.safe_name(),
            id = str(self._id),
        )
    
    @property
    def descendant_languages(self):
        descendant_languages = set()
        for relation in self.child_relations:
            if relation.destination != self:
                # first pass block infinite recursion
                descendant_languages.add(
                    relation.destination.language.name
                )
                descendant_languages.update(
                    relation.destination.descendant_languages
                )
        return descendant_languages
    
    @property
    def style_classes(self):
        return self.language.styles
    
    @property
    def style_class_names(self):
        return [style_class.name for style_class in self.style_classes]
    
    def is_detailed(self, detail_langs=None):
        if not detail_langs:
            return True
        if self.language.name in detail_langs:
            return True
        if self.descendant_languages.intersection(set(detail_langs)) != set():
            return True
    
    def dot_styling(self, session):
        dot_stlyings = [style_class.dot_styling for style_class in self.style_classes if style_class.dot_styling]
        styles = ", ".join(dot_stlyings)
        return styles
    
    @property
    def is_reconstruction(self):
        if self.transliteration and self.transliteration.startswith("*"):
            return True
        return False
    
    @property
    def is_attested(self):
        if self.transliteration and not self.transliteration.startswith("*"):
            return True
        elif self.orthography:
            return True
        return False
    
    @property
    def is_blank(self):
        if self.orthography:
            return False
        if self.transliteration:
            return False
        if self.transcription:
            return False
        return True
    
    # Output
    def dot_text(self, session, detail_langs=None):
        lines = deque()
        if self.is_detailed(detail_langs):
            node_description = [self.id,]
            
            attributes = list()
            
            label = f"label=<<TABLE BORDER=\"0\" CELLSPACING=\"0\" CELLPADDING=\"0\"><TR><TD>{self.language.name}</TD></TR>"
            if self.orthography:
                orthography_inner = self.orthography
                script = self.language.script_from_iso639(session)
                if script:
                    orthography_inner = f"<FONT FACE=\"{script.noto_fontname}\">{orthography_inner}</FONT>"
                label += f"<TR><TD>{orthography_inner}</TD></TR>"
            if self.transliteration:
                label += f"<TR><TD>&lt;{self.transliteration}&gt;</TD></TR>"
            if self.meaning:
                label += f"<TR><TD>\"{self.meaning}\"</TD></TR>"
            label += "</TABLE>>"
        
            attributes.append(label)
            attributes.append(self.dot_styling(session))
            #node styles
        
            node_description.append(f"[{', '.join(attributes)}]")
            if ", ," in ' '.join(node_description):
                import pdb; pdb.set_trace()
            lines.append(f"{' '.join(node_description)}\n")
        
            #if self.parent_relations:
                #lines.append(self.parent_relations.dot_text())
            #for relation in self.child_relations:
                #lines.append(relation.dot_text())
                #lines.extend(
                    #relation.destination.dot_text(session, detail_langs=detail_langs)
                #)
        
        return lines
        
    def html_text(self, parent_relation=None, family_footnotes=None):
        logging.debug(f"Generating HTML for word: {self!r}")
        family_footnotes = family_footnotes or OrderedDict()
        elems = list()
        li_class = list()
        li_class.extend(self.style_class_names)
        
        if self.child_relations:
            li_class.append("parent")
        if parent_relation:
            li_class.append(parent_relation.rel_type) #
            if parent_relation.guess:
                li_class.append("possible")
        else:
            pass
        
        elems.append("<li id='{id}' class='{classes}'>".format(
            id = self.id,
            classes = " ".join(li_class),
        ))
        
        if self.child_relations:
            if parent_relation is None or (self.orthography is None and self.transliteration is None) or "English" in self.descendant_languages:
                elems.append("<details open>")
            else:
                elems.append("<details>")
            elems.append("<summary class='{classes}'>".format(
                classes = " ".join(self.style_class_names),
            ))
        
        
        elems.append("<span class='{classes}' >{o.language.name}</span>".format(
            classes = " ".join(["language",]+self.style_class_names),
            o = self,
        ))
        
        if self.orthography:
            lang_tag = getattr(self.language, "iso639", "") or ""
            lang_attr = f"lang='{lang_tag}'"
            elems.append("<span class='{classes}' {lang_attr}>{o.orthography}</span>".format(
                classes = " ".join(["orthography",]+self.style_class_names),
                lang_attr = lang_attr,
                o = self,
            ))
        if self.transliteration:
            elems.append("<span class='transliteration' >{0.transliteration}</span>".format(self))
        if self.meaning:
            elems.append("<span class='meaning' >{0.meaning}</span>".format(self))
        if self.note:
            elems.append("<span class='note' >{0}</span>".format(html_safe(self.note)))
        if self.footnote_id:
            pass
            ix = list(family_footnotes.keys()).index(self.footnote_id)
            elems.append(
                "<sup id='footnote-link-{0}-a' class='note'><a href='#footnote-{0}'>[{0}]</a></sup>".format(ix+1)
            ) #replace 0 with index of footnote usage
        if self.child_relations:
            elems.extend(["</summary>","\n"])
        else:
            elems.extend(["</li>","\n"])
        
        if self.child_relations:
            elems.extend(["<ul>",])
            for relation in self.child_relations:
                elems.append(
                    relation.destination.html_text(
                        parent_relation = relation,
                        family_footnotes = family_footnotes,
                    )
                )
            elems.extend(["</ul>","</details>","</li>",])
        
        return "{0}\n".format(" ".join(elems))
    
    def to_database(self, session):
        assert self._db_id == None
        db_obj = db.Word(
                language_id = self.language.id,
                orthography = self.orthography,
                latin_transliteration = self.transliteration,
                uniquifier = self.uniquifier,
                meaning = self.meaning,
                inline_note = self.note,
            )
        session.add(db_obj)
        session.flush()
        self._db_id = db_obj.id
    
    # Input Factory
    
    @classmethod
    def from_raw(cls, raw_line, session, _id=0, check_unknown_langs=True):
        word_args = dict()
        try:
            markup_match = markup_pattern.search(raw_line)
            markup_match.groups()
        except AttributeError:
            import pdb; pdb.set_trace()
        
        level_str = markup_match.group("level")
        if level_str:
            level = level_str.count("-") + level_str.count("?")
            guess = level_str.count("?") > 0
        else:
            level = 0
            guess = False
        
        language_name = markup_match.group("language").strip()
        if not language_name:
           import pdb
           pdb.set_trace()
        
        try:
            language = db.Language.get_by_name(language_name, session)
        except ValueError as e:
            if language_name.startswith("Unknown"):
                pass
            elif language_name.startswith("?") or language_name.endswith("?"):
                pass
            elif check_unknown_langs:
                print(f"{language_name!r} for {raw_line} was not found in the language database.")
                answer = input(f"Continue with {language_name!r} as a generic language? (y)es or (N)o?\n")
                if answer.lower() in ["y","yes"]:
                    pass
                else:
                    raise e
            language = db.word_family.Language(
                    id = None,
                    name = language_name,
                    iso639 = None,
                )
                
        
        orth_str = markup_match.group("orthography")
        if orth_str:
            word_args["orthography"] = orth_str.strip("\`‎ ")
        
        transliteration_str = markup_match.group("transliteration")
        if transliteration_str:
            word_args["transliteration"] = transliteration_str.strip("<> ")
        
        transcription = markup_match.group("transcription") #not currently used
        
        uniquifier_str = markup_match.group("uniquifier")
        if uniquifier_str:
            word_args["uniquifier"] = int(uniquifier_str[1:])
        
        teaser_str = markup_match.group("teaser")
        if teaser_str:
            word_args["is_teaser"] = True
        
        meaning_str = markup_match.group("meaning")
        if meaning_str:
            word_args["meaning"] = meaning_str.strip("\"\": ")
        
        tags_str = markup_match.group("tags")
        if tags_str:
            word_args["tags"] = set(
                    [tag.strip().title() for tag in tags_str.strip("{}").split(",")]
                )
        
        note_str = markup_match.group("note")
        if note_str:
            word_args["note"] = note_str.strip("() ")
        
        footnote_str = markup_match.group("footnote")
        if footnote_str:
            word_args["footnote_id"] = footnote_str.count("#")
        
        word = cls(language, _id, **word_args)
        
        return level, guess, word


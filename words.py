# coding: utf-8

from collections import OrderedDict, deque
import logging
import re

import database as db

markup_pattern = re.compile(r"^(?P<level>[-?]+>)?\s*(?P<language>[^`<(#]+)(?P<orthography>\`[^`]+\`)?(?P<teaser>!)?\s*(?P<transliteration><[^>]+>)?\s*(?P<transcription>\[[^>]+\])?\s*(?P<meaning>: \"[^\"]+\")?\s*(?P<note>\([^\)]+\))?\s*(?P<footnote>[ ]*\#+)?")

def html_safe(text):
    if text:
        text = re.sub(r"<([^>]+)>", r"<span class='transliteration'>\1</span>", text)
        text = re.sub(r"\`([^`]+)\`(=([\w-]+))*", r"<span class='orthography' lang='\3'>\1</span>", text)
        text = re.sub(r"\[([^\]\|]+)\|([^\]\|]+)]", r"<a href='\1'>\2</a>", text)
        text = re.sub(r"(http\S+)", r"<a href='\1'>\1</a>", text)
        text = re.sub(r"href='wff-(\w+)'", r"href='/word-family-\1.html'", text)
        return text

class Word(object):
    
    _next_id = 1
    
    def __init__(self, language, orthography=None, is_teaser=False, transliteration=None, transcription=None, meaning=None, note=None, footnote_id=None):
        self.language = language
        self.orthography = orthography
        self.is_teaser = is_teaser
        self.child_relations = []
        self.transliteration = transliteration
        self.transcription = transcription #not currently used
        self.meaning = meaning
        self.note = note
        self.footnote_id = footnote_id
        self._id = self._next_id
        self.__class__._next_id += 1
        
    
    def __repr__(self):
        return f"{self.__class__.__name__}(language={self.language.name!r}, orthography={self.orthography!r}, transliteration={self.transliteration!r}, transcription={self.transcription!r}, meaning={self.meaning!r}, note={self.note!r})"
    
    def possible_match(self, other):
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
    
    # Output
    """font_names = []
        if self.orthography:
            script = self.language.script_from_bcp47(session)
            if script:
                font_names.extend(script.noto_fontname.split(", "))
        font_names = ", ".join(font_names)
        dot_stlyings.append(f'fontname="{font_names}"')
        """
    def dot_text(self, session, detail_langs=None):
        lines = deque()
        if self.is_detailed(detail_langs):
            node_description = [self.id,]
            
            attributes = list()
            
            label = f"label=<<TABLE BORDER=\"0\" CELLSPACING=\"0\" CELLPADDING=\"0\"><TR><TD>{self.language.name}</TD></TR>"
            if self.orthography:
                orthography_inner = self.orthography
                script = self.language.script_from_bcp47(session)
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
            lang_tag = getattr(self.language, "bcp47", "") or ""
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
    
    def to_database(self):
        pass
    
    # Input Factory
    
    @classmethod
    def from_raw(cls, raw_line, session, check_unknown_langs=True):
        try:
            markup_match = markup_pattern.search(raw_line)
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
            if check_unknown_langs:
                print(f"{language_name!r} for {raw_line} was not found in the language database.")
                answer = input(f"Continue with {language_name!r} as a generic language? (y)es or (N)o?\n")
                if answer.lower() in ["y","yes"]:
                    language = db.word_family.Language(
                        id = None,
                        name = language_name,
                        bcp47 = None,
                    )
                else:
                    raise e
            else:
                language = db.word_family.Language(
                    id = None,
                    name = language_name,
                    bcp47 = None,
                )
                
        
        orth_str = markup_match.group("orthography")
        if orth_str:
            orthography = orth_str.strip("\`‎ ")
        else:
            orthography = None
        teaser_str = markup_match.group("teaser")
        if teaser_str:
            is_teaser = True
        else:
            is_teaser = False
        
        transliteration_str = markup_match.group("transliteration")
        if transliteration_str:
            transliteration = transliteration_str.strip("<> ")
        else:
            transliteration = None
        
        meaning_str = markup_match.group("meaning")
        if meaning_str:
            meaning = meaning_str.strip("\"\": ")
        else:
            meaning = None
        
        note_str = markup_match.group("note")
        if note_str:
            note = note_str.strip("() ")
        else:
            note = None
        
        footnote_str = markup_match.group("footnote")
        if footnote_str:
            footnote_id = footnote_str.count("#")
        else:
            footnote_id = None
        
        word = cls(language, orthography=orthography, is_teaser=is_teaser, transliteration=transliteration, meaning=meaning, note=note, footnote_id=footnote_id)
        
        return level, guess, word


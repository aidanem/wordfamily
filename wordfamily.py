# coding: utf-8

from collections import OrderedDict, deque
import datetime
import logging
import os
import re

from words import Word, html_safe
import database as db

output_directory = "output"

# dot settings
RANKDIR = "LR"
OVERLAP = "false"
#LAYOUT = "twopi"
LAYOUT = "dot"
PENWIDTH = "2"

# control strings
date_start = re.compile('^date:[ ]*(\d\d\d\d\d\d\d\d)', re.I)
theme_start = re.compile('^theme:[ ]*(.*)', re.I)
tags_start = re.compile('^tags:[ ]*(.*)', re.I)
control_status = re.compile("(start|end)(intro|body|notes)", re.I)




class Family(object):
    
    def __init__(self, words, roots, focus_words, teaser_words=None, introduction=None, date=None, theme=None, tags=None, footnotes=None):
        self.words = words
        self.roots = roots
        self.focus_words = focus_words
        self._teaser_words = teaser_words
        self.introduction = introduction
        self.date = date or datetime.date.today()
        self.theme = theme
        
        self.tags = list()
        self.tags.append("Historical Linguistics")
        year = self.date.year
        self.tags.append("WFF-{year}".format(year=year))
        if tags:
            self.tags.extend(tags)
        
        self.footnotes = footnotes
    
    def __repr__(self):
        return "{cls}({words})".format(
            cls = self.__class__.__name__,
            words = ", ".join([repr(word) for word in self.words])
        )
    
    @property
    def teaser_words(self):
        if self._teaser_words is not None:
            return self._teaser_words
        elif len(self.focus_words) > 1:
            return self.focus_words
        else:
            return None
    
    # Dot Output
    def dot_file(self, filepath, session, detail_langs=None):
        
        dot_file_lines = deque()
        
        dot_file_lines.append('digraph WordFamily {\n')
        dot_file_lines.append(f'rankdir={RANKDIR}\n')
        dot_file_lines.append(f'overlap={OVERLAP}\n')
        dot_file_lines.append(f'layout={LAYOUT}\n')
        dot_file_lines.append(f'node [fontname="Noto Sans"]\n')
        dot_file_lines.append(f'edge [penwidth={PENWIDTH}]\n')
        
        for word in self.words:
            dot_file_lines.extend(word.dot_text(session, detail_langs=detail_langs))
            #import pdb; pdb.set_trace()
            for relation in word.child_relations:
                relation_line = relation.dot_text(detail_langs=detail_langs)
                if relation_line:
                    dot_file_lines.extend(relation_line)
        
        dot_file_lines.append('}\n')
        
        with open(filepath, "w") as file:
            
            for line in dot_file_lines:
                file.write(line)
    
    # html Output
    def html_file(self, filepath, name):
        
        if self.teaser_words is not None:
            teaser_word_text = ",\n".join(
                ['<a href="/word-family-{name}.html#{word.id}">{word.orthography}</a>'.format(
                    name = name,
                    word = word,
                )
                for word in self.teaser_words]
            )
        focus_word_text = ",\n".join(
            ['<a href="/word-family-{name}.html#{word.id}">{word.orthography}</a>'.format(
                name = name,
                word = word,
            )
            for word in self.focus_words]
        )
        with open(filepath, "w") as file:
            file.write("<html>\n")
            file.write("<head>\n")
            file.write("<title>Word Family - {0}</title>\n".format(name.capitalize()))
            file.write('<meta name="tags" content="{0}" />\n'.format(
                ", ".join(self.tags)
            ))
            file.write('<meta name="date" content="{date}" />\n'.format(
                date = self.date.isoformat()
            ))
            file.write('<meta name="category" content="Word Family" />\n')
            file.write("</head>\n")
            file.write("\n<body>\n")
            if self.theme:
                file.write("\n<h2>{month} theme: {theme}</h2>\n\n".format(
                    month = self.date.strftime("%B"),
                    theme = self.theme,
                ))
            if self.introduction:
                file.write("\n<h3>Introduction</h3>\n\n")
                for p in self.introduction:
                    file.write("<p>{0}</p>\n".format(html_safe(p)))
            if self.teaser_words:
                file.write("\n<h3>Teaser</h3>\n\n")
                file.write("\n<p>\n{0}\n</p>\n".format(teaser_word_text))
            file.write("\n<h3>Full Text</h3>\n")
            file.write("\n<ul class='wordfamily'>\n")
            for root in self.roots:
                file.write(root.html_text(family_footnotes=self.footnotes))
            file.write("</ul>\n\n")
            
            file.write("<h3>Visual</h3>\n")
            file.write('<p><a href="{{static}}/images/word_family/{0}.pdf"><img src="{{static}}/images/word_family/{0}.png" alt="Image is a visual representation of the text content above." style="max-width: 80%;"></a></p>\n\n'.format(name))
            
            if self.focus_words:
                file.write("<h3>Collected English words</h3>\n")
                file.write("<p>{0}</p>\n".format(focus_word_text))
            
            if self.footnotes:
                file.write("<h3>Footnotes</h3>\n")
                file.write("<ol class='footnotes'>\n")
                for ix, footnote in enumerate(self.footnotes.values()):
                    file.write("<li id='footnote-{0}'>\n".format(ix+1))
                    file.write("<span class='backlink'><a href='#footnote-link-{0}-a'>^</a></span>".format(ix+1))
                    for p in footnote:
                        file.write("<p>{0}</p>\n".format(html_safe(p)))
                    file.write("</li>\n")
                file.write("</ol>\n")
            file.write("</body>\n")
            file.write("</html>\n")
    
    def to_database(self):
        pass
    
    # Input Factory
    @classmethod
    def from_text(cls, filepath, session, focus=["English", "Translingual"], check_unknown_langs=True, auto_merge=False):
        session = db.default_session()
        word_lines = list()
        next_word_id = 1
        status = None
        date = None
        theme = None
        tags = None
        intro = list()
        footnotes = OrderedDict()
        with open(filepath, "r") as input_file:
            for raw_line in input_file.read().splitlines():
                if raw_line.strip():
                    control_status_match = control_status.match(raw_line)
                    if status is None:
                        date_control_match = date_start.match(raw_line)
                        if date_control_match:
                            date = datetime.datetime.strptime(
                                date_control_match.groups()[0],
                                "%Y%m%d",
                            ).date()
                            continue
                        theme_control_match = theme_start.match(raw_line)
                        if theme_control_match:
                            theme = theme_control_match.groups()[0]
                            continue
                        tags_control_match = tags_start.match(raw_line)
                        if tags_control_match:
                            tags_str = tags_control_match.groups()[0]
                            tags = [
                                item.strip() for item in tags_str.split(",")
                            ]
                            continue
                        
                        if control_status_match: 
                            if control_status_match.groups()[0] == "start":
                                status = control_status_match.groups()[1]
                    
                    elif control_status_match:
                        if control_status_match.groups()[0] == "end":
                            if status == control_status_match.groups()[1]:
                                status = None
                            else:
                                import pdb
                                pdb.set_trace()
                    
                    elif status == "intro":
                        intro.append(raw_line)
                    
                    elif status == "body":
                        level, guess, word = Word.from_raw(raw_line, session, next_word_id, check_unknown_langs=check_unknown_langs)
                        next_word_id += 1
                        for word_line in word_lines:
                            existing_word = word_line[2]
                            if word.possible_match(existing_word):
                                if auto_merge:
                                    word = existing_word
                                else:
                                    #prompt for merge
                                    print(f"Detected apparent duplicate word.\nExisting word: {existing_word!r}\nNew word: {word!r}")
                                    answer = input("Merge these two words? (y)es or (N)o?\n")
                                    if answer.lower() in ["y","yes"]:
                                        word = existing_word
                                    else:
                                        pass
                        word_lines.append((level, guess, word))
                        if word.footnote_id:
                            if word.footnote_id not in footnotes:
                                footnotes[word.footnote_id] = list()
                    
                    elif status == "notes":
                        if raw_line.startswith("#"):
                            #new note
                            id_str, text = raw_line.split(" ", 1)
                            id = id_str.count("#")
                            try:
                                footnotes[id].append(text)
                            except KeyError:
                                import pdb; pdb.set_trace()
                        else:
                            #continuing note
                            footnotes[id].append(raw_line)
        
        words = list()
        roots = list()
        focus_words = list()
        teaser_words = list()
        for ix, (level, guess, word) in enumerate(word_lines):
            if level == 0:
                roots.append(word)
            else:
                for (search_level, search_guess, search_word) in word_lines[0:ix][::-1]:
                    if search_level == level - 1:
                        if search_word.language == word.language:
                            rel_type = "derivative"
                        elif search_word.language in word.language.parents:
                            rel_type = "descent"
                        else:
                            rel_type = "borrowing"
                        relation = Relation(
                            source = search_word,
                            destination = word,
                            rel_type = rel_type,
                            guess = guess,
                        )
                        if relation not in search_word.child_relations:
                            search_word.child_relations.append(relation)
                        break
            if word not in words:
                words.append(word)
            if word.language.name in focus:
                if word not in focus_words:
                    focus_words.append(word)
            if word.is_teaser:
                if word not in teaser_words:
                    teaser_words.append(word)
        
        return cls(words, roots, focus_words, teaser_words, introduction=intro, footnotes=footnotes, date=date, theme=theme, tags=tags)



class Relation(object):
    
    def __init__(self, source, destination, rel_type, guess=False):
        self.source = source
        self.destination = destination
        self.rel_type = rel_type # descent, derivative, borrowing
        self.guess = guess
    
    def dot_text(self, detail_langs=None):
        
        if self.destination.is_detailed(detail_langs):
            parts = list()
            parts.append("{source.id} -> {destination.id}".format(
                source=self.source,
                destination=self.destination
            ))
            styles = list()
            if self.rel_type == "derivative":
                styles.extend(["arrowhead=diamond"])
            if self.rel_type == "borrowing":
                styles.extend(["arrowhead=invempty"])
            if self.guess:
                styles.extend(['style=dashed', 'label="?"'])
        
            if styles:
                parts.append("[{0}]".format(
                    ", ".join(styles)
                ))
            return "{0}\n".format(" ".join(parts))
    
    def to_database(self):
        pass
    
    def __hash__(self):
        return hash((
            str(self.source),
            str(self.destination),
            self.rel_type,
            self.guess,
        ))
    
    def __eq__(self, other):
        return all((
            self.source == other.source,
            self.destination == other.destination,
            self.rel_type == other.rel_type,
            self.guess == other.guess
        ))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type = str,
        help = "Word Family format file to use as input.",
        metavar = "FILEPATH",
    )
    parser.add_argument(
        '-d', '--detail-langs',
        metavar='LANG',
        type=str,
        nargs="*",
        help='One or more languages which details will be restricted to. Defaults to showing details for all languages.'
    )
    parser.add_argument(
        '-m', '--auto-merge',
        action = 'store_true',
        help = 'Automatically merge all matching words without asking.'
    )
    parser.add_argument(
        '-k', '--skip-html',
        action = 'store_true',
        help = 'Do not output html.'
    )
    parser.add_argument(
        '-v', '--verbose',
        action = 'store_true',
        help = 'Extra logging.'
    )
    
    args = parser.parse_args()
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)-8s [%(name)s] [%(threadName)s] %(message)s")
    
    session = db.default_session()
    
    word_family = Family.from_text(args.input, session, auto_merge=args.auto_merge)
    
    keyword = os.path.basename(args.input).split(".")[0]
    output_name_elements = [keyword,]
    output_name = "_".join(output_name_elements)
    
    if not args.skip_html:
        html_filename = f"{output_directory}/wff-{output_name}.html"
        word_family.html_file(html_filename, keyword)
    
    dot_filename = f"{output_directory}/{output_name}.gv"
    word_family.dot_file(dot_filename, session)
    
    detail_langs = list()
    if args.detail_langs:
        detail_langs.extend(args.detail_langs)
    else:
        detail_langs.extend(["English", "Translingual",])
    
    output_name_elements.append("detail")
    output_name_elements.extend(detail_langs)
    detail_output_name = "_".join(output_name_elements)
    detail_dot_filename = f"{output_directory}/{detail_output_name}.gv"
    word_family.dot_file(detail_dot_filename, session, detail_langs=detail_langs)
    
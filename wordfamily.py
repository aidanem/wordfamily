# coding: utf-8

from collections import defaultdict, OrderedDict, deque
import csv
import datetime
import logging
import os
import re

from words import Word, html_safe
import language_database as db

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
    
    def __init__(self, words, roots, focus_words, teaser_words=None, introduction=None, date=None, theme=None, footnotes=None):
        self.words = words
        self.roots = roots
        self.focus_words = focus_words
        self._teaser_words = teaser_words
        self.introduction = introduction
        self.date = date or datetime.date.today()
        self.theme = theme
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
    
    @property
    def tags(self):
        tags = set(["Historical Linguistics", f"WFF-{self.date.year!s}"]).union(
            *[word.tags for word in self.words]
        )
        
        return sorted(list(tags))
        
    
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
                [f'<a href="/word-family-{name}.html#{word.id}">{word.orthography}</a>'
                for word in self.teaser_words]
            )
        focus_word_text = ",\n".join(
            [f'<a href="/word-family-{name}.html#{word.id}">{word.orthography}</a>'
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
    
    def paths_file(self, filepath, detail_langs=None):
        paths = dict()
        for word in self.words:
            if detail_langs is None or word.language.name in detail_langs:
                for path in word.derivation_paths:
                    if path not in paths:
                        paths[path] = dict()
                        paths[path]["count"] = 0
                        paths[path]["words"] = set()
                    paths[path]["count"] += 1
                    paths[path]["words"].add(word)
        with open(filepath, "w") as file:
            paths_writer = csv.writer(file)
            paths_writer.writerow(["count", "path", "words"])
            for path, data in paths.items():
                paths_writer.writerow([
                    data["count"],
                    " > ".join([language.name for language in path]),
                    ", ".join([word.orthography or word.transliteration
                        for word in data["words"]
                        if word.orthography or word.transliteration])
                ])
    
    def to_database(self, session):
        relations = set()
        for word in self.words:
            logging.debug(f"Adding {word!r} to database")
            word.to_database(session)
            for relation in word.child_relations:
                relations.add(relation)
                logging.debug(f"Adding {relation!r} to queue")
        session.commit()
        session.flush()
        relation_type_id_map = Relation.relation_type_id_map(session)
        for relation in relations:
            logging.debug(f"Adding {relation!r} to database")
            relation.to_database(session, relation_type_id_map)
        session.commit()
    
    # Input Factory
    @classmethod
    def from_text(cls, filepaths, session, focus=["English", "Translingual"], check_unknown_langs=True, auto_merge=False):
        session = db.default_session()
        next_word_id = 1
        word_lines = list()
        words = list()
        roots = list()
        focus_words = list()
        teaser_words = list()
        intro = list()
        status = None
        date = None
        theme = None
        tags = None
        breadcrumb_trail = []
        
        footnotes = OrderedDict()
        for filepath in filepaths:
            logging.info(f"Reading words from {filepath}.")
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
                            level, guess, word = Word.from_raw(
                                    raw_line,
                                    session,
                                    next_word_id,
                                    check_unknown_langs=check_unknown_langs
                                )
                            next_word_id += 1
                            for existing_word in words:
                                if word.possible_match(existing_word):
                                    #import pdb; pdb.set_trace()
                                    if auto_merge:
                                        word = existing_word
                                    elif (word.uniquifier is not None and
                                            existing_word.uniquifier is not None and
                                            word.uniquifier == existing_word.uniquifier
                                            ):
                                        word = existing_word
                                    else:
                                        #prompt for merge
                                        print(f"Detected apparent duplicate word.\nExisting word: {existing_word!r}\nNew word: {word!r}")
                                        answer = input("Merge these two words? (y)es or (N)o?\n")
                                        if answer.lower() in ["y","yes"]:
                                            word = existing_word
                                        else:
                                            pass
                            #word_lines.append((level, guess, word))
                            if word.footnote_id:
                                if word.footnote_id not in footnotes:
                                    footnotes[word.footnote_id] = list()
                            if word not in words:
                                words.append(word)
                            if word.language.name in focus:
                                if word not in focus_words:
                                    focus_words.append(word)
                            if word.is_teaser:
                                if word not in teaser_words:
                                    teaser_words.append(word)
                            
                            breadcrumb_trail = breadcrumb_trail[:level]
                            if breadcrumb_trail:
                                parent_word = breadcrumb_trail[-1]
                                if parent_word.language == word.language:
                                    rel_type = "derivative"
                                    word.derivation_paths.extend([
                                            path+() for path in 
                                            parent_word.derivation_paths
                                        ])
                                elif parent_word.language in word.language.parents:
                                    rel_type = "descent"
                                    word.derivation_paths.extend([
                                            path+(word.language,) for path in 
                                            parent_word.derivation_paths
                                        ])
                                else:
                                    rel_type = "borrowing"
                                    word.derivation_paths.extend([
                                            path+(word.language,) for path in 
                                            parent_word.derivation_paths
                                        ])
                                relation = Relation(
                                    source = parent_word,
                                    destination = word,
                                    rel_type = rel_type,
                                    guess = guess,
                                )
                                if relation not in parent_word.child_relations:
                                    parent_word.child_relations.append(relation)
                                if relation not in word.parent_relations:
                                    word.parent_relations.append(relation)
                                
                            else:
                                roots.append(word)
                                word.derivation_paths.extend([(word.language,)])
                            breadcrumb_trail.append(word)
                    
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
        
        return cls(words, roots, focus_words, teaser_words, introduction=intro, footnotes=footnotes, date=date, theme=theme)



class Relation(object):
    
    def __init__(self, source, destination, rel_type, guess=False):
        self.source = source
        self.destination = destination
        self.rel_type = rel_type # descent, derivative, borrowing
        self.guess = guess
    
    def __repr__(self):
        return f"{self.__class__.__name__}(source={self.source}, destination={self.destination}, rel_type={self.rel_type}, guess={self.guess})"
    
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
    
    type_map_to_db = {
        "derivative": "synchronic_derivation",
        "descent": "diachronic_derivation",
        "borrowing": "borrowing",
    }
    
    @classmethod
    def relation_type_id_map(cls, session):
        return { key: session.query(
                db.DerivationType
            ).filter(
                db.DerivationType.name == value
            ).one().id for key, value in cls.type_map_to_db.items()}
    
    def to_database(self, session, relation_type_id_map):
        db_obj = db.Derivation(
                parent_id = self.source._db_id,
                child_id = self.destination._db_id,
                confident = not self.guess,
                derivation_type_id = relation_type_id_map[self.rel_type],
                #footnote_id,
            )
        session.add(db_obj)
    
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
        nargs="+",
        help = "Word Family format file to use as input.",
        metavar = "FILEPATH",
    )
    parser.add_argument(
        '-o', '--output-name',
        metavar='NAME',
        type=str,
        help='Name to use in output files. If no name is provided, it will be derived from the (first) inout file name.'
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
        '-b', '--database',
        action = 'store_true',
        help = 'Save information to the database.'
    )
    parser.add_argument(
        '-g', '--graphviz',
        action = 'store_true',
        help = 'Output graphviz file.'
    )
    parser.add_argument(
        '-p', '--paths',
        action = 'store_true',
        help = 'Output paths histogram file.'
    )
    parser.add_argument(
        '-t', '--html',
        action = 'store_true',
        help = 'Output html file.'
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
    
    if args.output_name:
        output_name = args.output_name
    else:
        output_name = os.path.basename(args.input[0]).split(".")[0]
    output_name_elements = [output_name,]
    output_name = "_".join(output_name_elements)
    
    if args.database:
        word_family.to_database(session)
    
    if args.html:
        html_filename = f"{output_directory}/wff-{output_name}.html"
        word_family.html_file(html_filename, output_name)
    
    if args.graphviz:
        dot_filename = f"{output_directory}/{output_name}.gv"
        word_family.dot_file(dot_filename, session)
    
    """if args.paths:
        paths_filename = f"{output_directory}/{output_name}.csv"
        word_family.paths_file(paths_filename)""" # only detail langs
    
    detail_langs = list()
    if args.detail_langs:
        detail_langs.extend(args.detail_langs)
    else:
        detail_langs.extend(["English", "Translingual",])
    
    output_name_elements.append("detail")
    output_name_elements.extend(detail_langs)
    detail_output_name = "_".join(output_name_elements)
    
    if args.graphviz:
        detail_dot_filename = f"{output_directory}/{detail_output_name}.gv"
        word_family.dot_file(detail_dot_filename, session, detail_langs=detail_langs)
    
    if args.paths:
        paths_filename = f"{output_directory}/{detail_output_name}.csv"
        word_family.paths_file(paths_filename, detail_langs=detail_langs)
    
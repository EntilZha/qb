import sqlite3
import random
from unidecode import unidecode
from collections import defaultdict, OrderedDict
import re

import string
punc = set(string.punctuation)
paren = re.compile("\\([^\\)]*\\)")


class Question:
    def __init__(self, qnum, answer, category, naqt,
                 tournaments, page, ans_type, fold, gender):
        self.qnum = qnum
        self.answer = answer
        self.category = category
        self.naqt = naqt
        self.tournaments = tournaments
        self.page = page
        self.ans_type = ans_type
        self.fold = fold
        self.gender = gender
        self.text = {}
        self._last_query = None
        self._cache_query = ""

    @staticmethod
    def cut_naqt_markup(sentence):
        return paren.sub("", sentence).replace("}", "").replace("{", "")

    def raw_words(self):
        """
        Return a list of all words, removing all punctuation and normalizing
        words
        """
        for ii in sorted(self.text):
            for jj in self.split_and_remove_punc(self.text[ii]):
                yield jj

    @staticmethod
    def split_and_remove_punc(text):
        for ii in text.split():
            word = "".join(x for x in unidecode(ii.lower()) if x not in punc)
            if word:
                yield word

    def partials(self, word_skip=-1):
        assert(isinstance(word_skip, int)), "Needs an integer %i" % word_skip
        for ii in sorted(self.text):
            previous = [self.text[x] for x in sorted(self.text) if x < ii]

            # TODO(jbg): Test to make sure this gives individual words
            # correctly if word_skip > 0
            if word_skip > 0:
                words = self.text[ii].split()
                for jj in xrange(word_skip, len(words), word_skip):
                    yield ii, jj, previous + [" ".join(words[:jj])]

            yield ii + 1, 0, [self.text[x] for x in sorted(self.text)
                              if x <= ii]

    def text_lines(self):
        d = {}
        d["id"] = self.qnum
        d["answer"] = unidecode(self.page)
        for ii in sorted(self.text):
            d["sent"] = ii
            d["text"] = unidecode(self.text[ii])
            yield d

    def get_text(self, sentence, token):
        if self._last_query != (sentence, token):
            self._last_query = (sentence, token)
            previous = ""
            for ii in xrange(sentence):
                previous += self.text.get(ii, "")
            if token > 0:
                previous += " ".join(self.text[sentence].split()[:token])
            self._cached_query = previous
        return self._cached_query

    def offset_to_partial(self, offset):
        """
        Given an offset in terms of words, convert it into sentence and word.
        """
        total_text = 0
        for ii in self.text:
            for jj in xrange(len(self.text[ii].split())):
                total_text += 1
                if total_text > offset:
                    return ii, jj
        return ii, jj

    def add_text(self, sent, text):
        self.text[sent] = text

    def random_text(self):
        cutoff = random.randint(0, max(self.text))
        return unidecode("\t".join(self.text[x] for x in sorted(self.text)
                                   if x <= cutoff))

    def flatten_text(self):
        return unidecode("\t".join(self.text[x] for x in sorted(self.text)))

    @staticmethod
    def fieldnames():
        return ["page", "answer", "fold", "id", "category", "naqt",
                "tournaments", "answer_type", "text"]

    def csv_row(self, random_text=False):
        yield "id", unicode(self.qnum)
        yield "answer", unidecode(self.answer)
        yield "category", unidecode(self.category)
        yield "naqt", unicode(self.naqt)
        yield "tournaments", unidecode(self.tournaments)
        yield "page", unidecode(self.page)
        yield "fold", unicode(self.fold)
        yield "answer_type", unidecode(self.ans_type)

        if random_text:
            yield "text", self.random_text()
        else:
            yield "text", self.flatten_text()


class QuestionDatabase:
    def __init__(self, location):
        self._conn = sqlite3.connect(location)

    def query(self, command, arguments, text=True):
        questions = {}
        c = self._conn.cursor()
        command = 'select id, page, category, answer, ' + \
            'tournament, type, naqt, fold, gender ' + command
        c.execute(command, arguments)

        for qq, pp, cc, aa, tt, kk, nn, ff, gg in c:
            questions[qq] = Question(qq, aa, cc, nn, tt, pp, kk, ff, gg)

        if text:
            for ii in questions:
                command = 'select sent, raw from text where question=? order by sent asc'
                c.execute(command, (ii, ))
                for ss, rr in c:
                    questions[ii].add_text(ss, rr)

        return questions

    def unmatched_answers(self, ids_to_exclude=set()):
        """
        Return a dictionary with the most unmatched pages
        """

        c = self._conn.cursor()
        command = 'select answer, id as cnt from questions ' + \
            'where page == ""'
        c.execute(command)

        answers = defaultdict(dict)
        for aa, id in c:
            normalized = aa.lower()
            normalized = normalized.replace("_", "")
            if not id in ids_to_exclude:
                answers[normalized][aa] = answers[normalized].get(aa, 0) + 1
        return answers

    def questions_by_answer(self, answer):
        questions = self.query('from questions where answer == ?', (answer,))

        for ii in questions:
            yield questions[ii]

    def question_by_id(self, id):
        questions = self.query('from questions where id == ?', (id,))

        for ii in questions:
            return questions[ii]

    def questions_with_pages(self):
        page_map = OrderedDict()

        questions = self.query('from questions where page != ""', ())
        questions = questions.values()

        for ii in sorted(questions, key=lambda x: x.answer):
            if not page_map.has_key(ii.page):
                page_map[ii.page] = []
            page_map[ii.page].append(ii)
        return page_map

    def questions_by_category(self, category, sort=None):
        questions = self.query('from questions where category == ?', (category,))

        if sort == 'decreasing_id':
            print("Sorting by %s" % sort)
            for ii in sorted(questions, reverse=True):
                yield questions[ii]
        elif sort == 'nopage_decreasing_id':
            print("Sorting by %s" % sort)
            for ii in sorted([x for x in questions if not questions[x].page], reverse=True):
                yield questions[ii]
            for ii in sorted([x for x in questions if questions[x].page], reverse=True):
                yield questions[ii]
        else:
            print("No sorting")
            for ii in questions:
                yield questions[ii]

    def associated(self, fold=None):
        c = self._conn.cursor()
        if fold:
            c.execute('select page, count(*) as cnt from questions where fold == "%s" group by page order by cnt desc' % fold)
        else:
            c.execute('select page, count(*) as cnt from questions group by page order by cnt desc')

        for pp, cc in c:
            yield pp

    def questions_by_page(self, page):
        # TODO(jbg): This is different usage than question_by_category; should
        # probably be fixed.
        return self.query('from questions where page == ?', (page,))

    def questions_by_tournament(self, tournament):
        return self.query('from questions where tournament like ?', ('%%%s%%' % tournament, ))

    def column_options(self, column, reduce=True):
        """
        Get all of the levels a column can take useful for getting a list of all
        the categories or types, for example.
        """
        c = self._conn.cursor()
        c.execute('select %s from questions group by %s' % (column, column))
        levels = set()
        for cc in c:
            if reduce:
                levels.add(cc[0].split(":")[0].lower())
            else:
                levels.add(cc)
        return levels

    def answer_by_count(self, category, min_count=1):
        """
        Return all answers that appear at least the specified number
        of times in a category.
        """
        c = self._conn.cursor()
        command = 'select answer, count(*) as num from questions where ' + \
                  'category="%s" ' % (category) + \
                  'group by answer order by num desc'
        c.execute(command)

        for aa, nn in c:
            if nn > min_count:
                yield aa

    def prune_text(self):
        """
        Remove sentences that do not have an entry in the database
        """

        c = self._conn.cursor()
        command = 'select id from questions group by id'
        c.execute(command)
        questions = set(x for x in c)

        c = self._conn.cursor()
        command = 'select question from text group by question'
        c.execute(command)
        text = set(x for x in c)

        orphans = text - questions

        c = self._conn.cursor()
        for ii in orphans:
            command = 'delete from text where question=%i' % ii
            c.execute(command)
        print("Keeping %i Pruning %i" % (len(questions - orphans),
                                         len(orphans)))
        self._conn.commit()

    def page_by_count(self, min_count=1):
        """
        Return all answers that appear at least the specified number
        of times in a category.
        """
        c = self._conn.cursor()
        command = 'select page, count(*) as num from questions where ' + \
                  'page <> "" ' + \
                  'group by answer order by num desc'
        c.execute(command)

        for aa, nn in c:
            if nn < min_count:
                continue
            else:
                yield aa

    def text_by_answer(self, answer, category):
        """
        Get all the text associated with an answer.
        """

        query = 'select raw from questions INNER JOIN text on ' + \
          'id=question where answer=? and category=?;'

        c = self._conn.cursor()
        c.execute(query, (answer, category))

        for tt in c:
            yield tt[0]

    def get_all_pages(self):
        c = self._conn.cursor()
        c.execute('select page from questions where page != "" group by page')
        for cc in c:
            yield cc[0]

    def majority_frequency(self, page, column):
        """
        Given a page, look up the majority value for a column and its frequency
        """

        c = self._conn.cursor()
        c.execute('SELECT ?, count(*) AS cnt FROM questions WHERE page=? ' +
                  'GROUP BY ? ORDER BY cnt DESC', (column, page, column, ))
        total = 0
        majority = None
        majority_count = 0
        for pp, cc in c:
            print pp, cc
            if majority is None:
                majority = pp
                majority_count = cc
            total += cc

        if total > 0:
            return majority, float(majority_count) / float(total)
        else:
            return majority, -1

    def all_answers(self):
        """
        Return a lookup from IDs to pages
        """
        d = {}
        c = self._conn.cursor()
        command = "select id, page from questions where page != ''"
        c.execute(command)

        for ii, pp in c:
            d[int(ii)] = pp
        return d

    def set_type_by_page(self, type_assignment, page):
        query = "UPDATE questions SET type=? WHERE page=?"
        c = self._conn.cursor()
        c.execute(query, (page, type_assignment))
        self._conn.commit()

    def set_all_answer_pages(self, category, answer, page, type):
        query = "UPDATE questions SET page=?, type=? WHERE category=? and answer=?"
        c = self._conn.cursor()
        c.execute(query, (page, type, category, answer))
        self._conn.commit()

    def set_all_answer_pages(self, category, answer, page, type):
        query = "UPDATE questions SET page=?, type=? WHERE category=? and answer=?"
        c = self._conn.cursor()
        c.execute(query, (page, type, category, answer))
        self._conn.commit()

    def set_answer_page(self, qid, page, ans_type):
        query = "UPDATE questions SET page=?, type=? WHERE id=?"
        c = self._conn.cursor()
        c.execute(query, (page, ans_type, qid))
        self._conn.commit()


if __name__ == "__main__":
    db = QuestionDatabase("data/non_naqt.db")
    print(list(db.answer_by_count("Literature", 3)))

    print(list(db.text_by_answer("Kazuo _Ishiguro_", "Literature")))

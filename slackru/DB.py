""" All SQLite database interactions should route through a DB instance """

import sqlite3


class Base:
    def __init__(self, dbpath):
        self.dbpath = dbpath
        self.conn = None
        self.c = None

    def get(self):
        self.conn = sqlite3.connect(self.dbpath)

        def make_dicts(cursor, row):
            return dict((cursor.description[idx][0], value)
                        for idx, value in enumerate(row))

        self.conn.row_factory = make_dicts
        self.c = self.conn.cursor()
        return self

    def close(self):
        self.conn.close()

    def execAndCommit(self, *args):
        self.c.execute(*args)
        self.conn.commit()


class Init(Base):
    def __init__(self, dbpath):
        Base.__init__(self, dbpath)

        self.get()

        if self.isEmpty():
            self.create_all()

    def isEmpty(self):
        self.c.execute('SELECT name FROM sqlite_master WHERE type="table";')
        return self.c.fetchall() == []

    def create_all(self):
        self.create_mentors()
        self.create_shifts()
        self.create_questions()
        self.create_posts()

    def drop_table(self, table_name):
        self.c.execute("DROP TABLE IF EXISTS " + table_name)
        self.conn.commit()

    def drop_all(self):
        self.drop_table('mentors')
        self.drop_table('shifts')
        self.drop_table('questions')
        self.drop_table('posts')

    def create_mentors(self):
        self.execAndCommit("CREATE TABLE mentors "
                           "(userid TEXT PRIMARY KEY, "
                           "name TEXT, "
                           "username, "
                           "keywords VARCHAR(1000))")

    def create_shifts(self):
        self.execAndCommit("CREATE TABLE shifts "
                           "(userid TEXT, "
                           "start TEXT, "
                           "end TEXT, "
                           "FOREIGN KEY(userid) REFERENCES mentors(userid))")

    def create_questions(self):
        self.execAndCommit("CREATE TABLE questions "
                           "(id INTEGER PRIMARY KEY, "
                           "question TEXT, "
                           "answered INTEGER, "
                           "username TEXT, "
                           "userid TEXT, "
                           "timestamp INTEGER, "
                           "matchedMentors BLOB, "
                           "assignedMentor TEXT, "
                           "FOREIGN KEY(assignedMentor) REFERENCES mentors(userid))")

    def create_posts(self):
        self.execAndCommit("CREATE TABLE posts "
                           "(questionId INTEGER, "
                           "userid TEXT, "
                           "channel TEXT, "
                           "timestamp TEXT, "
                           "FOREIGN KEY(questionId) REFERENCES questions(id), "
                           "FOREIGN KEY(userid) REFERENCES mentors(userid))")


class DB(Init):
    def __init__(self, dbpath):
        Init.__init__(self, dbpath)

    def runQuery(self, query, args=(), one=False):
        cur = self.conn.execute(query, args)
        rv = cur.fetchall()
        cur.close()

        return (rv[0] if rv else None) if one else rv

    def insertMentor(self, name, username, userid, keywords):
        CMD = "INSERT INTO mentors " \
              "(name, username, userid, keywords) " \
              "VALUES (?, ?, ?, ?)"
        self.execAndCommit(CMD, [name, username, userid, keywords])

    def insertShift(self, userid, start, end):
        CMD = "INSERT INTO shifts " \
              "(userid, start, end) " \
              "VALUES (?, ?, ?)"
        self.execAndCommit(CMD, [userid, start, end])

    def insertQuestion(self, question, username, userid, matchedMentors):
        CMD = "INSERT INTO questions " \
              "(question, answered, username, userid, timestamp, matchedMentors, assignedmentor) " \
              "VALUES (?, 0, ?, ?, datetime('now', 'localtime'), ?, NULL)"
        self.execAndCommit(CMD, [question, username, userid, matchedMentors])
        return self.c.lastrowid

    def insertPost(self, questionId, userid, channel, timestamp):
        CMD = "INSERT INTO posts " \
              "(questionId, userid, channel, timestamp) " \
              "VALUES (?, ?, ?, ?)"
        self.execAndCommit(CMD, [questionId, userid, channel, timestamp])

    def markAnswered(self, userid, questionId):
        CMD = "UPDATE questions " \
              "SET answered=1, " \
              "assignedMentor=? " \
              "WHERE id=?"

        self.execAndCommit(CMD, [userid, questionId])

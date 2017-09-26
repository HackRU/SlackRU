from flask import Flask
import sqlite3
import config
app = Flask(__name__)
dbpath = config.dbpath
def get_db():
    """
    From the Flask Websitei, probs best practice to connect to the databse this way
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(dbpath)
    return db
def query_db(query, args=(), one=False):
    """
    Query function from flask documentation to avoid the usage of a raw cursor
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.route("/pairmentor")
def pairMentor(methods = ['POST']):
    return "Hello World!"

#the twilio end point that will text mentors
def pairMentorWithHacker(comment:str,username:str):
    """
    pairs a mentor with a hacker using the kwywords from the senntence
    :param comment:str -> the input string the parse
    :param username:str -> the username of the person asking the question
    """
    query = query_db('SELECT * from keywords')
    #build a list of keywords
    keywordlist = []
    mentorlist = []
    for keyword in query:
        keywordlist.append(keyword['keyword'])
    for word in comment:
        if word.lower() in keywordlist:
            q = query_db('SELECT id from keywords WHERE keyword='+word.lower())
            #selec all the mentors 
            if q is not None:
                mentorsublist = query_db("SELECT * from mentors WHERE keyid="+q)


    
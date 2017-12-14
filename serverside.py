from flask import Flask, request
from DB import DB
import config
import util
from twilio.rest import Client
import time
import json
import queue
import threading

app = Flask(__name__)
dbpath = config.dbpath
db = DB(dbpath)  # Initializes Database
ph = config.twilioph
queueOfTimes = queue.Queue()

# setup twilio with sid and authid
client = Client(config.sid, config.authid)


def query_db(query, args=(), one=False):
    """
    Query function from flask documentation to avoid the usage of a raw cursor
    """
    cur = db.conn.execute(query, args)
    rv = cur.fetchall()
    cur.close()

    return (rv[0] if rv else None) if one else rv


@app.route("/pairmentor", methods=['POST'])
def pairMentor():
    """
        Route that client sends the question to
    """
    jsonrequest = request.form.to_dict()
    print(jsonrequest)
    dat = jsonrequest['data']
    user = jsonrequest['user']
    userid = jsonrequest['userid']
    textMentorsQuestion(dat, user, userid)
    return "done"


# the twilio end point that will text mentors
def textMentorsQuestion(comment: str, username: str, userid: str) -> None:
    """
     Given a question , tries to find mentors with the keywords and sends a message that a hacker needs help
    :param comment:str -> the input string the parse
    :param username:str -> the username of the person asking the question
    """
    q_test = 0
    epoch = int(time.time())
    mentorlist = []
    # select all the mentors
    q = query_db("SELECT * from mentors")
    for keywordlist in q:

        li = keywordlist['keywords'].split(',')

        for word in comment.split():
            if word in li:
                mentorlist.append(keywordlist)
                break
        # Text All mentors
    # if no mentors, text all mentors asking the question
    if mentorlist == []:
        for i in q:
            mentorlist.append(i)
    li = json.dumps(mentorlist)
    li2 = json.dumps([])
    db.conn.execute("INSERT into activequestions (answered,username,userid,timestamp,phones,peoplewhoans,assignedmentor) VALUES(?,?,?,?,?,?,?)",
                    [0, username, userid, epoch, li, li2, None])
    db.conn.commit()
    q_test = query_db("SELECT last_insert_rowid()", one=True)
    queueOfTimes.put(epoch)

    for mentor in mentorlist:
        # message all the mentor
        sendMessage(mentor['phone'], "hi, a hacker had a question, " + comment + " " + "please type accept " + str(q_test['last_insert_rowid()']) + " to accept" + " or " + "decline " + str(q_test['last_insert_rowid()']) + " to decline")


@app.route('/makeRequest', methods=['POST'])
def makeRequest():
    """
        The Route that handles responded to the user after they accept or decline
    """
    from_no = request.form['From']
    print(from_no)
    body = request.form['Body'].lower()
    if len(body.split()) != 2:
        sendMessage(from_no, "please fix your formatting, either accept <id> or decline <id>")
    else:

        splitBody = body.split()
        if splitBody[0] == 'accept':
            # grab the id and check
            id_ = query_db("SELECT id,answered,peoplewhoans,userid from activequestions WHERE id=?", [int(splitBody[1])], one=True)

            print("The ID Is" + str(id_))
            id_chec = id_['id']
            people = json.loads(id_['peoplewhoans'])
            people.append(from_no)
            db.conn.execute('UPDATE activequestions SET peoplewhoans=? WHERE id=?', [json.dumps(people), id_chec])
            db.conn.commit()

            if id_['answered'] == 1:
                sendMessage(from_no, "Hi, Another mentor has already accepted this question")
            else:
                # append to answered question sql table
                # message the user via slack using the util class as we are storing the USERNAME of the person
                name = query_db('select name from mentors where phone=?', [from_no], one=True)
                util.message(id_['userid'], "Hi You Have been paired with " + name['name'] + " , please goto the mentor table and meet " + name['name'] + " your question id is " + str(id_chec))
                db.conn.execute('UPDATE activequestions SET answered=? WHERE id=?', [1, id_chec])

                db.conn.commit()

                db.conn.execute('UPDATE activequestions SET assignedmentor=? WHERE id=?', [name['name'], id_chec])
                db.conn.commit()

                sendMessage(from_no, "Hi, You have been assigned this question, please goto the mentor desk and find the hacker")
        elif splitBody[0] == 'decline':
            # append to the people who answered thing and then check if
            ans_ = query_db('SELECT peoplewhoans,phones,answered,userid FROM activequestions WHERE id=?', [int(splitBody[1])], one=True)
            peoplewhoans = json.loads(ans_['peoplewhoans'])
            phones = json.loads(ans_['phones'])
            peoplewhoans.append(from_no)
            sendMessage(from_no, 'Thanks for responding')
            db.conn.execute('UPDATE activequestions SET peoplewhoans=? WHERE id=?', [json.dumps(peoplewhoans), int(splitBody[1])])
            db.conn.commit()
            # scan the list and check if all the people responded and the answered state is false
            phlist = []
            brokeFunctions = False
            for i in phones:
                phlist.append(i['phone'])

            for j in phlist:
                print(j)
                if j not in peoplewhoans:
                    brokeFunctions = True
                    break
            if brokeFunctions is False and ans_['answered'] == 0:
                util.message(ans_['userid'], "All mentors are busy, please try again in a few miniutes")

    return "done"


def messageHackersToTryAgain(id_: int):
    """
        When all mentors respond No, it is been 10 minutes and no mentor has accepted

    """
    print(id_)
    # select from the databse
    question = query_db("SELECT * from activequestions WHERE id=?", [id_], one=True)
    if question['answered'] == 0:
        util.message(question['userid'], "All mentors are busy, please try again later in 10 or 15 min")
        # call out mentors who ignored
        # SELECT from the DB
        listofphones = json.loads(question['phones'])
        peoplewhoans = json.loads(question['peoplewhoans'])
        for i in listofphones:
            if i['phone'] not in peoplewhoans:
                sendMessage(i['phone'], "Hi, To Ensure the smoothness of the hackathon, please respond to all requests with either accept or decline")


def schedulequeueScan():
    if queueOfTimes.qsize() > 0:
        ep = queueOfTimes.get()
        with app.app_context():
            quest = query_db("SELECT * from activequestions WHERE timestamp = ?", [ep], one=True)
            currentepoch = int(time.time())
            if ((currentepoch - quest['timestamp']) > 600):
                messageHackersToTryAgain(quest['id'])
            else:
                queueOfTimes.put(quest['timestamp'])
    # every 5 min run the scanner
    threading.Timer(300.0, schedulequeueScan).start()


schedulequeueScan()


def sendMessage(to: str, message: str) -> None:
    """
        Helper method to send messages
        :param to:str -> the phone numner to send to
        :param message:str -> the message we send
    """

    message = client.messages.create(to, body=message, from_=ph)


if __name__ == '__main__':
    app.run(debug=True)

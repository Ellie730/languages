import spacy
import sqlite3

from datetime import date, datetime
from flask import redirect, render_template, session
from functools import wraps

languages = ["Finnish", "French", "German", "Italian", "Spanish"]

con = sqlite3.connect("languagecards.db", check_same_thread=False)
db = con.cursor()

def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code



def lemmatise(text, language):

    #load the correct 
    if language == "Italian":
        
        nlp = spacy.load("it_core_news_sm")
    
    if language == "Spanish":

        nlp = spacy.load("es_core_news_sm")

    doc = nlp(text)

    lemmas = [token.lemma_ for token in doc]
    return lemmas


    
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function



def presence(variable, vname):

    if not variable:
        return apology(f"please enter a {vname}")
    
    else:
        return 



def update():

        #if new day reset new card counter
    db.execute ("SELECT time FROM users WHERE id = ?", (session["user_id"],))
    last = date.fromtimestamp(int(float(db.fetchall()[0][0])))

    session["datetime"] = datetime.now().timestamp()
    today = date.today()
    if last != today:
        for language in languages:
            session.update({f"{language}":{"new_seen":0, "reviewed":0}})
    session["zerror"] = True
    if session["zerror"] ==  True:
        session[session["language"]]["reviewed"] = 0
    #find the number of cards to review
    db.execute("""UPDATE users SET time = ?, finnish_ns = ?, french_ns = ?, german_ns = ?, italian_ns = ?, spanish_ns = ? WHERE id = ?""",
               (session["datetime"], session["Finnish"]["new_seen"], session["French"]["new_seen"], session["German"]["new_seen"], session["Italian"]["new_seen"], session["Spanish"]["new_seen"], session["user_id"]))
    db.execute("""SELECT COUNT (*) FROM user_progress
    WHERE due < ? AND user_id = ? AND word_id IN 
    (SELECT id FROM words WHERE language = ?)"""
    , (session["datetime"], session["user_id"], session["language"]))
    count = db.fetchall()[0][0]
    if count>0:
        session[session["language"]]["review_count"] = count
        session["zerror"] = False
    else:
        session[session["language"]]["review_count"] = 1
        session[session["language"]]["reviewed"] = 1
        session["zerror"] = True
    db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    session["new_cards"] = int(db.fetchall()[0][5])
    con.commit()
    
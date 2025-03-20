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

    if language == "Finnish":
        
        nlp = spacy.load("fi_core_news_sm")

    if language == "French":

        nlp = spacy.load("fr_core_news_sm")

    if language == "German":

        nlp = spacy.load("de_core_news_sm")

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
    try:
        last = date(db.fetchall()[0][0])
    except IndexError:
        last = 0
    
    session["datetime"] = datetime.now().timestamp()
    if last != date.today():
        for language in languages:
            session.update({f"{language}":{"new_seen":0, "reviewed":0}})
        
    #find the number of cards to review
    db.execute("""SELECT COUNT (*) FROM user_progress
    WHERE due < ? AND user_id = ? AND word_id IN 
    (SELECT id FROM words WHERE language = ?)"""
    , (session["datetime"], session["user_id"], session["language"]))
    session[session["language"]]["review_count"] = db.fetchall()
    db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    session["new_cards"] = db.fetchall()[0][5]
    #update the time in the database
    db.execute("""UPDATE users SET time = ? WHERE id = ?""", (session["datetime"], session["user_id"]))
    con.commit()
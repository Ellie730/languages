import sqlite3

from collections import Counter
from datetime import datetime
from flask import Flask, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, presence, update, lemmatise

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = "plumbingfailure"

with app.app_context():  
    con = sqlite3.connect("languagecards.db", check_same_thread=False)
    db = con.cursor()

@app.route("/")
@login_required
def index():

    update()
    
    db.execute(
    """SELECT * FROM decks JOIN users_to_decks ON decks.deck_id = users_to_decks.deck_id 
    WHERE user_id = ? AND decks.language = ?"""
    , (session["user_id"], session["language"]))
    decks = db.fetchall()
    for deck in decks:
        if deck[7] is None:
            db.execute ("UPDATE decks SET size=0 WHERE deck_id=?",(deck[0],))
            con.commit()
        db.execute("""SELECT COUNT (*) FROM user_progress WHERE state = "learning" OR state = "learned" AND user_id = ? 
        AND word_id IN (SELECT word_id FROM deck_contents WHERE deck_id = ?)""",
        (session["user_id"], deck[9]))
        known = db.fetchall()[0][0]
        db.execute("""SELECT SUM (frequency) FROM user_progress 
        WHERE user_id = ? AND word_id IN 
        (SELECT word_id FROM deck_contents WHERE deck_id = ?)""", (session["user_id"], deck[0]))
        frequency = db.fetchall()[0][0]
        if frequency is None:
            frequency = 1
        db.execute ("""SELECT SUM (frequency) FROM user_progress 
        WHERE state = "learning" OR state = "learned" AND user_id = ? AND word_id IN 
        (SELECT word_id FROM deck_contents WHERE deck_id = ?)""", (session["user_id"], deck[0]))
        weighted = db.fetchall()[0][0]
        if weighted is None:
            weighted = 1
        db.execute("""UPDATE users_to_decks SET progress = ?, weighted = ? 
        WHERE deck_id = ? AND user_id = ?""", (known/int(deck[7]), weighted/frequency,deck[0], session["user_id"]))
        con.commit()
    db.execute ("SELECT deck_order FROM users WHERE id = ?",(session["user_id"],))
    order = db.fetchall()[0][0]
    db.execute("SELECT * FROM decks JOIN users_to_decks ON decks.deck_id = users_to_decks.deck_id WHERE user_id = ? ORDER BY ?", (session["user_id"], order))
    display = db.fetchall()
    return render_template ("mainpage.html", display = display, user = session["user_id"])



@app.route("/change_language")
@login_required
def change_language():

    language = request.args.get("language")
    session["language"] = language
    db.execute ("UPDATE users SET language = ? WHERE id = ?", (language, session["user_id"]))
    con.commit()
    return redirect("/")



@app.route("/change_status", methods=["POST"])
@login_required
def change_status():
    status = request.form.get("status")
    id = request.form.get("deck_id")
    if status == "Public":
        db.execute ("UPDATE decks SET status = private WHERE deck_id = ?", (id,))
    if status == "Private":
        db.execute ("UPDATE decks SET status = public WHERE deck_id = ?", (id,))
    con.commit()
    return redirect ("/")



@app.route("/edit_deck", methods=["POST"])
@login_required
def edit_deck():

    # check if the current user is the creator of the deck 
    deck = request.form.get("deck_id")
    db.execute ("SELECT creator FROM decks WHERE deck_id = ?", (deck,))
    creator = db.fetchall()[0][0]

    #else make a new deck that contains the same info, to be edited
    if session["user_id"] != int(creator):
        db.execute ("SELECT * FROM decks WHERE deck_id = ?", (deck,))
        deck_info = db.fetchall()
        db.execute ("""INSERT INTO decks (language, name, medium, genre, author, date, size, creator, public) values (?,?,?,?,?,?,?,?, 'private')"""
        , (session["language"], deck_info[0][2], deck_info[0][5], deck_info[0][6], deck_info[0][3], deck_info[0][4], deck_info[0][7], session["user_id"]))
        db.execute("SELECT * FROM users_to_decks WHERE user_id = ? AND deck_id = ?", (session["user_id"], deck))
        user_info = db.fetchall()
        db.execute("SELECT deck_id FROM decks WHERE name = ? AND creator = ?", (deck_info[0][2], session["user_id"]))
        edited_id = db.fetchall()
        db.execute ("""INSERT INTO users_to_decks (user_id, deck_id, progress, position, weighted) VALUES (?,?,?,?,?)"""
        , (session["user_id"], edited_id[0][0], user_info[0][2], user_info[0][3], user_info[0][4]))
        db.execute ("DELETE FROM users_to_decks WHERE user_id = ? AND deck_id = ?", (session["user_id"], deck))
        con.commit()
        session["deck_id"] = edited_id[0][0]

    else:
        session["deck_id"] = deck
    
    return redirect ("/input")



@app.route("/input", methods=["GET", "POST"])
@login_required
def input():
        
    if request.method == "POST":
        input_type = request.form.get("input_type")
        #display the page
        if not input_type:
            return render_template("input.html", deck = session["deck_id"])
        
        # if a file is inputted, read it into a variable, split the string into a list of words
        if input_type == "f":
            with open (request.form.get("input")) as file:
                text = file.read()
                
        if input_type == "t":
            text = request.form.get("input")

        # lemmatise each word and get a list of words and their frequencies
        lemmatised = lemmatise(text, session["language"])
        contents = Counter(lemmatised)

        # create list of all words that have been created already 
        existing = []
        db.execute("SELECT * FROM words WHERE language = ? AND common = Common", (session["language"],))
        created = db.fetchall()
        for word in created:
            existing.append(created[word]["word"])
        
        #create a list of all words in this deck
        db.execute("""SELECT word_id FROM deck_contents WHERE deck_id = ?""", (session["deck_id"],))
        deck_words = db.fetchall()
        deck_contents = []
        for word in deck_words:
            deck_contents.append(deck_words[word][0])
        
        #create a list of the user's words
        db.execute("""SELECT word_id FROM user_progress WHERE user_id = ? AND word_id IN (
        SELECT word_id FROM words WHERE language = ?)""", (session["user_id"], session['language']))
        uwords = db.fetchall()
        user_words = []
        for word in uwords:
            user_words.append(uwords[word]["word_id"])

        #for each word, if it is new create a card. 
        session["uncommon"] = []

        need_lookup = []

        for word in contents.keys():
            if word not in existing:
                need_lookup.append(word)

        session["need_lookup"] = need_lookup
        
        values = create_card(need_lookup, session["language"])
        
        for word in values:

            #if data cannot be found it is an uncommon word, store for later
            if not values[word]["translation"]:
                session["uncommon"].append(word)
                session["uncommon_frequency"].append(contents[word])
            else:
                db.execute (
                """INSERT INTO words (word, language, definition, frequency, part, common) VALUES(?,?,?,?,?,common)"""
                , (word, session["language"], values["definition"], values["frequency"], values["part"])
                )
                con.commit

        for word in contents:
            # TODO: rework deck updates
            # if the word is not in this deck, add it to the deck
            db.execute ("SELECT id FROM words WHERE word = ? AND language = ? AND public = public", (word,))
            word_id = db.fetchall()[0][0]
            if word_id not in contents:
                db.execute("INSERT INTO deck_contents (deck_id, word_id, frequency) VALUES (?,?,?)", (session["deck_id"], word_id, contents[word]))
            # if the word is in the deck, add the frequency value
            else:
                db.execute ("SELECT frequency FROM deck_contents WHERE word_id = ?", (word_id,))
                frequency = db.fetchall()[0][0] + contents[word]
                db.execute ("UPDATE deck_contents SET frequency = ? WHERE word_id = ?", (frequency, word_id))
            
            # add the card to user_progress or update frequency
            if word_id not in user_words:
                db.execute ("""INSERT INTO user_progress 
                (user_id, word_id, viewings, easy, good, ok, some, none, state, frequency) VALUES
                (?,?,0,0,0,0,0,0,new,?)""", (session["user_id"], word_id, contents[word]))
            else:
                db.execute("""SELECT frequency FROM user_progress WHERE user_id = ? AND word_id = ?""",
                (session["user_id"], word_id))
                frequency = db.fetchall()[0][0] + contents[word]
                db.execute("""UPDATE user_progress SET frequency = ? WHERE user_id = ?, word_id = ?""", (frequency, session["user_id"], word_id))

        db.execute ("SELECT COUNT(*) FROM deck_contents WHERE deck_id = ?", (session["deck_id"],))
        size = db.fetchall()[0][0]
        db.execute("""UPDATE decks SET size = ? WHERE deck_id = ?""", (size, session["deck_id"]))
        con.commit()

        return redirect ("/uncommon")

    else:
        return render_template("input.html")





@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "POST":

        # check that username and password have been entered
        username = request.form.get("username")
        presence (username, "username")
        password = request.form.get("password")
        presence (password, "password")

        # check that these values are correct
        db.execute("SELECT * FROM users WHERE username = ?", (username,))
        rows = db.fetchall()

        if len(rows) != 1 or not check_password_hash(
            rows[0][2], request.form.get("password")
        ):
            return apology("incorrect username and or password", 403)
        
        # create session with the person's id, storing other key settings
        session["user_id"] = rows[0][0]
        session["language"] = rows[0][3]
        session["deck_order"] = rows[0][6]
        session["card_order"] = rows[0][4]

        return redirect("/")           

    #if method is GET, render the login form
    else:
        return render_template("login.html")


    
@app.route("/logout")
@login_required
def logout():

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



@app.route("/my_deck")
@login_required
def my_deck():

    #display 50 cards in the deck
    page = int(request.args.get("page"))
    db.execute ("SELECT size FROM decks WHERE deck_id  = ?", (session["deck_id"],))
    pages = int((db.fetchall()[0][0] - 1)/50)
    db.execute ("SELECT card_order FROM users WHERE id = ?", (session["user_id"],))
    order = db.fetchall()[0][0]
    db.execute (""" SELECT * from words
    JOIN user_progress ON words.id = user_progress.word_id
    WHERE id IN (SELECT word_id FROM deck_contents WHERE deck_id = ?) AND user_id = ?
    ORDER BY ? LIMIT ?, 50""", (session["deck_id"], session["user_id"], order, 50*page))
    cards = db.fetchall()
    return render_template ("deck.html", cards = cards, page = page, pages=pages)



@app.route("/new_deck", methods = ["GET", "POST"])
@login_required
def new_deck():
    
    if request.method == "POST":
        #get the required variables from the form
        language = request.form.get ("language")
        presence(language, "language")
        if language != session["language"]:
            session["language"] = language
            db.execute("UPDATE users SET language = ? WHERE id = ?", (language, session["user_id"]))
        name = request.form.get("name")
        presence(name, "name")
        medium = request.form.get("medium")
        genre = request.form.get("genre")
        author = request.form.get("author")
        date = request.form.get("date")
        #use the decks table to enter this data
        db.execute("INSERT INTO decks (language, name, medium, genre, author, date, size, creator, public) VALUES (?,?,?,?,?,?,1,?, 'private')"
                   , (language, name, medium, genre, author, date, session["user_id"]))   
        con.commit()
        db.execute("SELECT deck_id FROM decks WHERE name = ?", (name,))
        session["deck_id"] = db.fetchall()[0][0]
        try:
            db.execute("SELECT position FROM users_to_decks ORDER BY position DESC LIMIT 1")
            position = db.fetchall()[0][0] + 1
        except IndexError:
            position = 0
        db.execute("""INSERT INTO users_to_decks (user_id, deck_id, position) VALUES (?,?,?)""", (session["user_id"], session["deck_id"], position))
        con.commit()
        return redirect ("/input")

    else: 
        return render_template("new_deck.html")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        # check that a username password and confirmation have been entered
        username = request.form.get("username")
        presence (username, "username")
        password = request.form.get("password")
        presence (password, "password")
        confirm = request.form.get("confirm")
        presence (confirm, "confirmation")

        # check that password and username are valid
        if password != confirm:
            return apology("confirmation does not match password", 403)
        db.execute("SELECT COUNT (*) FROM users WHERE username = ?", (username,))
        check_username = db.fetchall()
        if check_username == 1:
            return apology("This username is already taken", 403)
        
        # input new user into database
        hash = generate_password_hash(password)
        db.execute ("INSERT INTO users (username, hash, language) VALUES (?, ?, Italian)", (username, hash))
        con.commit()
        return redirect ("/")

    else:
        return render_template ("register.html")



@app.route("/review")
@login_required
def review():

    update(db)
    #decide what the next card to show is and display it

    #if the reviewed percentage is greater than the new percentage, show a new card
    if session[session["language"]]["new_seen"]/session["new_cards"] < session[session["language"]]["reviewed"]/session[session["language"]]["review_count"] and session[session["language"]]["new_seen"] < session["new_cards"]:
        db.execute ("""SELECT * FROM user_progress 
        JOIN words ON user_progress.word_id = words.id 
        WHERE user_progress.user_id = ? AND user_progress.state = new AND word_id IN 
        (SELECT word_id FROM deck_contents WHERE deck_id = ?)
        ORDER BY ? LIMIT 1""", (session["user_id"], session["deck_id"], session["order"]))
        card = db.fetchall()
        session["state"] = "new"

    #if possible, choose the longest overdue card with interval < 1 hr
    else:
        db.execute ("""SELECT * FROM user_progress 
        JOIN words ON user_progress.word_id = words.id 
        WHERE user_progress.user_id = ? AND user_progress.state = seen AND words.language = ? 
        AND user_pogress.due < ? AND user_progress.interval < 3600
        ORDER BY due LIMIT 1""", (session["user_id"], session["language"], datetime.now()))
        card = db.fetchall()

        session["state"] = "review"

        # if there is no short interval card, choose long interval card
        if not card:
            db.execute ("""SELECT * FROM user_progress 
            JOIN words ON user_progress.word_id = words.id 
            WHERE user_progress.user_id = ? AND user_progress.state = seen AND words.language = ? 
            AND user_pogress.due < ? 
            ORDER BY due LIMIT 1""", (session["user_id"], session["language"], datetime.now()))
            card = db.fetchall()
    
    # if there are any short interval cards to review, do so before ending the session
    if not card:
        db.execute ("""SELECT * FROM user_progress 
        JOIN words ON user_progress.word_id = words.id 
        WHERE user_progress.user_id = ? AND user_progress.state = seen AND words.language = ? 
            AND user_progress.interval < 3600
        ORDER BY due LIMIT 1""", (session["user_id"], session["language"]))
        card = db.fetchall()
    
    # if there are no cards left to review, display session over
    if not card:
        return render_template ("end_review.html", count = session[session["language"]]["reviewed"], new = session[session["language"]]["new_seen"])

    else:
        session["card"]= card[0]["words.id"]
        return render_template ("review.html", card = card)
    
            

@app.route ("/search_decks", methods=["GET", "POST"])
@login_required
def search_decks ():
    
    if request.method == "POST":

        id = request.form.get ("id")
        name = request.form.get("name")
        medium = request.form.get("medium")
        genre = request.form.get("genre")
        author = request.form.get("author")
        date = request.form.get("date")
    
        db.execute("""SELECT * FROM decks WHERE id = ?  AND language = ? AND name LIKE ? AND medium LIKE ? AND genre LIKE ? AND author LIKE ? AND date LIKE ? AND public = public"""
        , (id, session["language"], name, medium, genre, author, date))
        matching = db.fetchall()
        return render_template ("found.html", matching = matching)

    else:
        return render_template ("search_decks.html")



@app.route("/settings", methods = ["GET", "POST"])
@login_required
def settings ():
    
    if request.method == "POST":
        
        #update card order
        card_order = request.form.get ("card_order")
        if card_order:
            db.execute ("UPDATE users SET card_order = ? WHERE user_id = ?", (card_order, session["user_id"]))
            
        #update number of new cards
        new_cards = int(request.form.get ("new_cards"))
        if new_cards:
            db.execute ("UPDATE users SET new_cards = ? WHERE user_id = ?", (new_cards, session["user_id"]))

        #update deck order
        deck_order = request.form.get ("deck_order")
        if deck_order:
            db.execute ("UPDATE users SET deck_order = ? WHERE user_id = ?", (deck_order, session["user_id"]))
        con.commit()
        return redirect("/settings")
       
    else:
        return render_template ("settings.html")



@app.route("/show_card", methods = ["GET", "POST"])
@login_required
def show_card():

    if request.method =="POST":       

        #reset time
        update()

        #get the value of multiplier
        multiplier = request.form.get("multiplier")

        #get the last interval
        db.execute("SELECT interval FROM user_progress")
        interval = db.fetchall()[0][0]

        #if interval is longer than a day, do the maths
        if interval >= 86400:
            if multiplier > 0:
                interval *= multiplier
                if interval < 86400:
                    interval = 86400
            else:
                interval = 600

            if multiplier != 0.05:
                due = interval + session["datetime"]
            else:
                due = 900 + session["datetime"]

        #if not, use the preset values for short periods
        else: 
            if multiplier == 0:
                interval = 600
            elif multiplier == 0.05:
                interval = 43200
            elif multiplier == 1:
                interval = 86400
            elif multiplier == 2:
                interval = 345600
            else:
                interval = 846000
            due =  interval + session["datetime"]

        # update the database with this data
        db.execute ("SELECT * FROM user_progress WHERE user_id = ? AND word_id = ?", (session["user_id"], session["card"]))
        viewings = db.fetchall()[0]
        db.execute("""UPDATE user_progress SET due = ? seen = ? interval = ? viewings = ?
        WHERE user_id = ? AND word_id = ?""", (due, session["datetime"], interval, viewings["viewings"] + 1, session["user_id"], session["card"]))
        
        #update the specific viewing category
        if multiplier == 0:
            db.execute("""UPDATE user_progress SET none = ? WHERE user_id = ? AND word_id = ?"""
            , (viewings["none"] + 1, session["user_id"], session["card"]))
        elif multiplier == 0.05:
            db.execute("""UPDATE user_progress SET some = ? WHERE user_id = ? AND word_id = ?"""
            , (viewings["some"] + 1, session["user_id"], session["card"]))
        elif multiplier == 1:
            db.execute("""UPDATE user_progress SET okay = ? WHERE user_id = ? AND word_id = ?"""
            , (viewings["okay"] + 1, session["user_id"], session["card"]))
        elif multiplier == 2:
            db.execute("""UPDATE user_progress SET good = ? WHERE user_id = ? AND word_id = ?"""
            , (viewings["good"] + 1, session["user_id"], session["card"]))
        elif multiplier == 3:
            db.execute("""UPDATE user_progress SET easy = ? WHERE user_id = ? AND word_id = ?"""
            , (viewings["easy"] + 1, session["user_id"], session["card"]))
        
        #if already seen, update state and the number of reviews
        if session["state"] == "review":
            if interval < 2500000:
                db.execute ("""UPDATE user_progress SET state = learned WHERE user_id = ? AND word_id = ?"""
                , (session["user_id"], session["card"]))
            else:
                db.execute("""UPDATE user_progress SET state = learning WHERE user_id = ? AND word_id = ?"""
                , (session["user_id"], session["card"]))
            session[session["language"]]["reviewed"] += 1
        
        #if the card was new change state to learning, and count a new card seen
        else:
            db.execute("""UPDATE user_progress SET state = learning WHERE user_id = ? AND word_id = ?"""
            , (session["user_id"], session["card"]))
            session[session["language"]]["new_seen"] +=1
        
        con.commit()
        return redirect ("/review")

    else:

        db.execute("""SELECT * from words JOIN user_progress ON user_progress.word_id = words.id 
        WHERE words.id = ? and user_id = ?""", (session["card"], session["user_id"]))
        card = db.fetchall()
        return render_template("show_card.html", card = card)



@app.route("/uncommon", methods = ["GET", "POST"])
@login_required
def uncommon():

    if request.method == "POST":
        definition = request.args.get("definition")
        frequency = request.args.get("frequency")
        example = request.args.get("example")
        part = request.args.get("part")
        
        if definition:
            db.execute("""INSERT INTO words (language, word, definition, frequency, example, part, common) 
            VALUES (?,?,?,?,?,?, uncommon)""", (session["language"], session["uncommon"][0], definition, frequency, example, part))
            db.execute("""INSERT INTO user_progress (user_id, word_id, viewings, easy, good, ok, some, none, state, frequency) 
            VALUES (?,(SELECT id FROM words WHERE word = ? AND language = ? AND definition = ? and common = uncommon),0,0,0,0,0,0, new)""",
            (session["user_id"], session["uncommon"][0], session["language"], definition, session["uncommon_frequency"][0]))
            db.execute ("""INSERT INTO deck_contents (deck_id, word_id, frequency) 
            VALUES (?,(SELECT id FROM words WHERE word = ? AND language = ? AND definition = ? and common = uncommon),?)""", (session["deck_id"], session["uncommon"][0], session["language"], definition, session["uncommon_frequency"][0]))

        con.commit()
        session["uncommon"].pop(0)
        session["uncommon_frequency"].pop(0)
        return redirect ("/uncommon")


    else:
        #pick the next word that hasn't been dealt with
        word = session["uncommon"][0]
    
        if not word:
            return redirect ("/")

        else:
            return render_template ("uncommon.html", word = word)
        
@app.route("/view_deck", methods=["POST"])
@login_required
def view_deck():
    session["deck_id"] = request.form.get("deck")
    return redirect ("/my_deck?page=0")
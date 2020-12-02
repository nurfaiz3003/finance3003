import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    record = db.execute("SELECT * FROM record WHERE id = :id", id=session["user_id"])
    cash = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
    counter = 0
    stockcash = 0

    for x in record:
        symbol = record[counter]["symbol"]
        stock = lookup(symbol)
        record[counter]["name"] = stock["name"]
        record[counter]["price"] = stock["price"]
        record[counter]["total"] = stock["price"] * record[counter]["shares"]
        stockcash = stockcash + record[counter]["total"]
        counter = counter + 1
    sum = cash[0]["cash"] + stockcash
    return render_template("index.html", records=record, cash=cash[0]["cash"], sum=sum)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if lookup(request.form.get("symbol")) is None:
            return render_template("buy.html", warning="Stocks not found.")
        
        id = session["user_id"]
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        cash = db.execute("SELECT * FROM users WHERE id = :id", id=id)
        stocks = lookup(symbol)

        if (stocks["price"] * int(shares)) > cash[0]["cash"]:
            return render_template("buy.html", warning="Insufficient Money.")
        
        pay = cash[0]["cash"] - (stocks["price"] * int(shares))
        db.execute("UPDATE users SET cash = :pay WHERE id = :id", pay=pay, id=id)
        
        if not db.execute("SELECT * FROM record WHERE symbol = :symbol", symbol=symbol):
            db.execute("INSERT INTO record (id, symbol, shares) VALUES (:id, :symbol, :shares)", id=id, symbol=symbol, shares=shares)
        else:
            db.execute("UPDATE record SET shares = shares + :shares WHERE symbol = :symbol", shares=shares, symbol=symbol)
        
        db.execute("INSERT INTO history (id, symbol, shares, price, transacted) VALUES (:id, :symbol, :shares, :price, CURRENT_TIMESTAMP)", id=id, symbol=symbol, shares=shares, price=stocks["price"] * int(shares)*-1)
        
        flash('Bought!')
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    history = db.execute("SELECT * FROM history WHERE id = :id", id=session["user_id"])
    return render_template("history.html", histories=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if lookup(request.form.get("symbol")) is None:
            return render_template("quote.html", warning="Stocks not found.")

        stock = lookup(request.form.get("symbol"))
        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=stock["price"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        
        user=request.form.get("username")
        hashpass=generate_password_hash(request.form.get("password"))

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide a username", 403)
        
        # Ensure email was submitted
        elif not request.form.get("password"):
            return apology("must provide an password", 403)
        
        # Ensure matching password
        elif not request.form.get("checkpass") or request.form.get("checkpass") != request.form.get("password"):
            return apology("password not match", 403)

        #Query existing username
        namecheck = db.execute("SELECT * FROM users WHERE username = :username", username=user)
        
        #Check if username already exist
        if len(namecheck) > 0:
            return apology("Username Already Exist", 403)
        
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=user, hash=hashpass)
        
        return render_template("login.html", warning="Registered! Please Login..")

    else:
        return render_template("register.html") 

@app.route("/addcash", methods=["GET", "POST"])
def addcash():
    if request.method == "POST":
        add = float(request.form.get("add"))
        db.execute("UPDATE users SET cash = cash + :add WHERE id = :id", add=add, id=session["user_id"])
        flash("Success!")
        currentcash = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        return render_template("addcash.html", currentcash=currentcash[0]["cash"])
        
    else:
        currentcash = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        return render_template("addcash.html", currentcash=currentcash[0]["cash"])

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute("SELECT symbol FROM record WHERE id = :id", id=session["user_id"])
    if request.method == "POST":
        stock = db.execute("SELECT shares FROM record WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=request.form.get("stocks"))
        if stock[0]["shares"] < int(request.form.get("shares")):
            return render_template("sell.html", stocks=stocks, warning="Insufficient Shares.")
        
        shares = stock[0]["shares"] - int(request.form.get("shares"))
        if shares == 0:
            db.execute("DELETE FROM record WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=request.form.get("stocks"))
        else:
            db.execute("UPDATE record SET shares = :shares WHERE id = :id AND symbol = :symbol", shares=shares, id=session["user_id"], symbol=request.form.get("stocks"))

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        stockprice = lookup(request.form.get("stocks"))
        stockpay = int(request.form.get("shares")) * stockprice["price"]
        pay = cash[0]["cash"] + stockpay
        db.execute("UPDATE users SET cash = :pay WHERE id = :id", pay=pay, id=session["user_id"])
        db.execute("INSERT INTO history (id, symbol, shares, price, transacted) VALUES (:id, :symbol, :shares, :price, CURRENT_TIMESTAMP)", id=session["user_id"], symbol=request.form.get("stocks"), shares=int(request.form.get("shares"))*-1, price=stockpay)
         
        flash('Sold!')
        return redirect("/")
    else:
        return render_template("sell.html", stocks=stocks)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

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
db = SQL("postgres://rqorbrmkogjmvc:e6358648c6080f00eac3e216ba231b0dc42850f85080497752996d1a9662b990@ec2-107-21-216-112.compute-1.amazonaws.com:5432/ddd211o8enk6bb")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get user cash balance
    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = cash[0]["cash"]

    # initialise total portfolio value to cash
    portfolio_value = cash

    # returns list of dict of each stock details
    stocks = db.execute(
        "SELECT symbol, SUM(shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol ", user_id=session["user_id"])
    for stock in stocks:

        # get fresh stock data
        quote = lookup(stock["symbol"])
        print(quote)

        # store stock data in stocks to be passed onto index.html
        stock["name"] = quote["name"]
        stock["value"] = stock["SUM(shares)"] * quote["price"]
        stock["total_value"] = usd(stock["SUM(shares)"] * quote["price"])
        stock["price"] = usd(quote["price"])
        print(stock["price"])

        # increment total portfolio value by value of each stock
        portfolio_value += stock["value"]

    return render_template("index.html", stocks=stocks, cash=cash, portfolio_value=portfolio_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # if user submitted a form
    if request.method == "POST":
        symbol = str(request.form.get("symbol"))
        shares = request.form.get("shares")

        # check if inputs are filled
        if not symbol:
            return apology("You must provide a symbol")
        elif not shares:
            return apology("You must provide the number of shares")

        # validate number of stocks wished to buy is positive
        if not shares.isdigit():
            return apology("You must buy a positive integer of shares")
        elif int(shares) <= 0:
            return apology("You must buy a positive integer of shares")

        shares = int(shares)

        # get stock information
        quote = lookup(symbol)

        # validate stock
        if not quote:
            return apology("Stock is invalid")
        else:
            price = quote["price"]

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        cash = cash[0]["cash"]

        # if user can afford to buy
        if cash >= shares * price:

            # add transaction details to transactions table
            db.execute(
                "INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", user_id=session['user_id'], symbol=symbol, shares=shares, price=price)

            # update cash in users table after purchase
            db.execute("UPDATE users SET cash = cash - :expense WHERE id = :id", expense=shares*price, id=session["user_id"])

            return redirect("/")

        # if user is broke
        else:
            return apology("You broke")

    # if user clicked a link
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    username = request.args.get("username")

    result = db.execute("SELECT username FROM users WHERE username = :username", username=username)

    if not result and len(username) > 0:
        return jsonify(True)
    else:
        return jsonify(False)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # returns list of dict of each stock details
    transactions = db.execute(
        "SELECT symbol, shares, price, timestamp FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    # iterate over every transaction
    for transaction in transactions:

        # get fresh stock data
        quote = lookup(transaction["symbol"])

        # store stock data in stocks to be passed onto index.html
        transaction["name"] = quote["name"]

        # if bought shares
        if transaction["shares"] > 0:
            transaction["status"] = "Bought"

        # if sold shares
        else:
            transaction["status"] = "Sold"
            transaction["shares"] = -transaction["shares"]

    return render_template("history.html", transactions=transactions)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

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


@app.route("/reset_password", methods=["GET", "POST"])
@login_required
def reset_password():
    """Changes user's password"""

    if request.method == "POST":
        user_id = session["user_id"]
        print("Yes")

        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        # if user hasnt made a typo
        if new_password == confirmation:
            new_hash = generate_password_hash(new_password)
            db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=new_hash, user_id=session["user_id"])
            print("Got here")
            return render_template("reset_success.html")

        # if user made a typo
        else:
            print("Not this")
            return apology("Your passwords don't match. Typo?")

    else:
        print("Weird")
        return render_template("reset_password.html")


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
    """Get stock quote."""

    # if user submitted a form
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # if stock is invalid
        if not quote:
            return apology("Stock is invalid")

        # if stock is valid
        else:
            quote["price"] = usd(quote["price"])
            return render_template("quoted.html", quote=quote)

    # if user clicked a link
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # if user submitted the form
    if request.method == "POST":

        # store inputs in convinient variables
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check all inputs are filled
        if not username:
            return apology("Missing username!")
        elif not password:
            return apology("Missing password!")
        elif not confirmation:
            return apology("Please type your password again!")

        # check passwords match
        if password != confirmation:
            return apology("The passwords you typed don't match.")

        # hash password
        hash = generate_password_hash(password)

        # insert user into database
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
        if not result:
            return apology("Username already taken.")

        # stores user id in session
        session["user_id"] = result

        return redirect("/")

    # if user clicked on a link
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # if user submitted the form
    if request.method == "POST":
        stocks = db.execute(
            "SELECT symbol, SUM(shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol ", user_id=session["user_id"])

        symbol = request.form.get("symbol")

        # validate stock selection
        if not symbol:
            return apology("You must select a stock to sell")

        shares_to_sell = int(request.form.get("shares"))

        shares_held = db.execute(
            "SELECT SUM(shares) FROM transactions WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=symbol)

        # valiadte stock ownership
        if not shares_held:
            return apology("You don't own that stock")

        shares_held = int(shares_held[0]["SUM(shares)"])

        # validate stock number
        if shares_to_sell <= 0:
            return apology("You must sell at least 1 stock")
        elif shares_to_sell > shares_held:
            return apology("You don't have enough stocks")

        quote = lookup(symbol)
        price = quote["price"]

        # log selling transaction as buying negative stocks
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", user_id=session['user_id'], symbol=symbol, shares=-shares_to_sell, price=price)

        # update cash in users table after purchase
        db.execute("UPDATE users SET cash = cash + :revenue WHERE id = :id", revenue=shares_to_sell*price, id=session["user_id"])

        return redirect("/")

    # if user clicked a link
    else:
        # returns list of dict of each stock details
        stocks = db.execute(
            "SELECT symbol, SUM(shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol ", user_id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

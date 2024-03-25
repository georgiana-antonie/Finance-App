import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

USERNAME = ""

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #Obtain portfolio information from the database
    rows = db.execute("SELECT sum(shares) as shares, symbol, price, sum(total) as total FROM portfolio WHERE user_id = ? GROUP BY symbol",
                       session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]["cash"]

    sum = cash
    # Filter out rows with zero or negative shares
    new_rows = [row for row in rows if row['shares'] > 0]

    for row in new_rows:
        stock = lookup(row["symbol"])
        sum += int(row["shares"]) * (stock["price"])
        profit = (row["shares"]) * (stock["price"]) - (row["total"])

        # Format stock price, total, and profit as USD
        row["price"] = usd(stock["price"])
        row["total"] = usd(row["total"])
        row["profit"] = usd(profit)
        row["value_now"] = usd(row["shares"] * stock["price"])
        row["prfl"] = profit

    return render_template("index.html", rows=new_rows, cash=usd(cash), sum=usd(sum), username=USERNAME)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        # Get symbol and shares from the form data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        #Ensure symbol is not blank
        if not symbol:
            return apology("must provide symbol", 400)

        #Ensure shares is not blank
        if not shares:
            return apology("must provide shares", 400)

        # Ensure shares is not blank and can be converted to an integer
        try:
            shares = int(shares)
        except ValueError:
            return apology("must introduce an integer", 400)

        shares = int(shares)
        #Ensure no. of shares is not a positive integer
        if shares < 0:
            return apology("must introduce a positive number", 400)

        stock = lookup(symbol)

        # Check if stock exist
        if not stock:
            return apology("invalid stock symbol", 400)

        cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)[0]["cash"]

        stock_price = float(stock["price"])
        total_price = stock_price * shares

        #Check if cash is enough
        if cash <= total_price:
            return apology("More fund required", 400)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - total_price, user_id)
        db.execute("INSERT INTO portfolio (user_id, symbol, shares, price, total, transaction_type) VALUES (?, ?, ?, ?, ?, ?)",
                       user_id, symbol, shares, stock_price, total_price, 'buy')

        # Flash a message indicating successful buy
        flash('Bought!')

        # Redirect to the homepage
        return redirect("/")

    else:
        symbol = request.form.get("symbol")
        cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)[0]["cash"]
        return render_template("buy.html", username=USERNAME, cash=usd(cash))



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "GET":
        rows = db.execute("SELECT * FROM portfolio WHERE user_id=?", session["user_id"])
        return render_template("history.html", rows=rows, username=USERNAME)


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
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        global USERNAME
        USERNAME = db.execute("SELECT username FROM users WHERE id=?", session["user_id"])[0]["username"]
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", username=USERNAME)


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
    if request.method == "POST":
        symbol = request.form.get("symbol")

        #Ensure symbol is not blank
        if not symbol:
            return apology("must provide symbol", 400)

        stock = lookup(symbol)

        # Check if stock exist
        if not stock:
            return apology("invalid stock symbol", 400)

        return render_template("quoted.html", symbol=stock, username=USERNAME)

    else:
        return render_template("quote.html", username=USERNAME)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Get username and password from the form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not confirmation:
            return apology("must provide confirmation", 400)

        # Ensure password match with confirmation
        if password != confirmation:
            return apology("the passwords do not match", 400)

        # Query database to ensure username isn't already taken
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)
        if len(rows) != 0:
            return apology("username is already taken", 400)

        #Saving data in the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Get symbol and shares from the form data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        #Ensure symbol is not blank
        if not symbol:
            return apology("must provide symbol", 400)

        #Ensure shares is not blank
        if not shares:
            return apology("must provide shares", 400)

        shares = int(shares)
        #Ensure no. of shares is a positive integer
        if shares < 0:
            return apology("must introduce a positive number", 400)

        # Lookup stock information
        stock = lookup(symbol)

        # Check if stock exist
        if not stock:
            return apology("invalid stock symbol", 400)

        available_shares = db.execute("SELECT sum(shares) AS shares FROM portfolio WHERE symbol = ? AND user_id=?", stock["symbol"], session["user_id"])[0]["shares"]

        # Check if the user has enough shares to sell
        if shares > int(available_shares):
            return apology("there are not that many shares in the portfolio", 400)

        db.execute("INSERT INTO portfolio (user_id, symbol, shares, price, total, transaction_type) VALUES (?,?,?,?,?,?)",
                   session["user_id"], stock["symbol"], -shares, stock["price"], -(shares*stock["price"]), "sell")

        # Update user's cash balance after selling shares
        cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", int(cash)+(shares*stock['price']), session["user_id"])

        # Flash a message indicating successful sale
        flash('Sold!')

        # Redirect to the homepage
        return redirect("/")

    else:
        rows = db.execute("SELECT sum(shares) as shares, symbol FROM portfolio WHERE user_id = ? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", rows=rows, username=USERNAME)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
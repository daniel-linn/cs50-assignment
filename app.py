import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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
    user_id = session.get("user_id")

    stocks = db.execute(
        "SELECT symbol, number_s FROM stock_users WHERE user_id = ? ORDER BY symbol", user_id)
    rows = []
    total = 0

    for stock in stocks:
        stock_s = stock['symbol']
        stock_n = stock['number_s']
        stock_p = lookup(stock_s)["price"]
        stock_t = stock_n * stock_p
        total = total + stock_t
        rows.append({'symbol': stock_s, 'shares': stock_n, 'price': stock_p, 'total': stock_t})

    cash_t = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_t[0]['cash']
    total = total + cash

    return render_template("index.html", rows=rows, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("check your symbol")
        elif lookup(symbol) == None:
            return apology("symbol not exsists")

        symbol = symbol.upper()

        number_stock = request.form.get("shares")
        if not number_stock:
            return apology("check your number")
        try:
            number_stock = int(number_stock)
        except ValueError:
            return apology("check your number")

        if number_stock < 0:
            return apology("check your number")

        price = float(lookup(symbol)["price"])
        total_price = price * number_stock
        user_id = session.get("user_id")

        account_t = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        account = account_t[0]['cash']

        if account < total_price:
            return apology("you don't have enough money")

        # check if there is storage of stock
        symbol_t = db.execute(
            "SELECT symbol FROM stock_users WHERE symbol = ? AND user_id = ?", symbol, user_id)

        transaction_time = datetime.now()

        if symbol_t == []:
            db.execute("INSERT INTO stock_users(number_s, symbol, price, user_id) VALUES (?, ?, ?, ?)",
                       number_stock, symbol, price, user_id)
            db.execute("INSERT INTO transactions (number_s, price, symbol, user_id, action, timestamps) VALUES (?, ?, ?, ?, ?, ?)",
                       number_stock, price, symbol, user_id, "Buy", transaction_time)
        else:
            stock_number_c = db.execute(
                "SELECT number_s FROM stock_users WHERE symbol = ? AND user_id = ?", symbol, user_id)
            stock_number_c1 = stock_number_c[0]['number_s']
            new_stock_number = stock_number_c1 + number_stock
            db.execute("UPDATE stock_users SET number_s = ?, price = ? WHERE symbol = ? AND user_id = ?",
                       new_stock_number, price, symbol, user_id)
            db.execute("INSERT INTO transactions (number_s, price, symbol, user_id, action, timestamps) VALUES (?, ?, ?, ?, ?, ?)",
                       number_stock, price, symbol, user_id, "Buy", transaction_time)

        account_new = account - (lookup(symbol)["price"] * number_stock)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", account_new, user_id)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    user_id = session.get("user_id")

    history = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)
    """Show history of transactions"""

    return render_template("history.html", history=history)


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
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("check your symbol")

        if lookup(symbol) == None:
            return apology("symbol not exsists")

        quoted = lookup(symbol)

        price = usd(quoted["price"])

        return render_template("quoted.html", name=symbol, price=price)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        name = request.form.get("username")
        if not name:
            return apology("must provide username")

        password = request.form.get("password")
        if not password:
            return apology("must provide password")

        check = request.form.get("confirmation")
        if check != password:
            return apology("Check your input and try again!")

        hashed_password = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, hashed_password)
        except ValueError:
            return apology("Username exists!")

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session.get("user_id")

    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("check your input")
        elif lookup(symbol) == None:
            return apology("symbol not exsists")

        symbol = symbol.upper()

        number = request.form.get("shares")
        if not number:
            return apology("check your input")
        try:
            number = int(number)
        except ValueError:
            return apology("check your input")
        if number < 0:
            return apology("check your input")

        container1 = db.execute(
            "SELECT symbol, number_s FROM stock_users WHERE symbol = ? AND user_id = ?", symbol, user_id)
        stock_n = container1[0]['number_s']
        transaction_time = datetime.now()

        if container1 == []:
            return apology("you don't have the stock")
        if number > stock_n:
            return apology("you don't have enough stocks to sell")

        new_stock_n = stock_n - number
        if new_stock_n == 0:
            db.execute("DELETE FROM stock_users WHERE symbol = ? AND user_id = ?", symbol, user_id)
        else:
            db.execute("UPDATE stock_users SET number_s = ? WHERE user_id = ? AND symbol = ?",
                       new_stock_n, user_id, symbol)

        price = lookup(symbol)["price"]
        profit = price * number
        accout_t = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        accout = accout_t[0]['cash']
        new_accout = profit + accout
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_accout, user_id)
        db.execute("INSERT INTO transactions (number_s, price, symbol, user_id, action, timestamps) VALUES (?, ?, ?, ?, ?, ?)",
                   number, price, symbol, user_id, "Sell", transaction_time)

        return redirect("/")

    else:

        rows = db.execute("SELECT symbol FROM stock_users WHERE user_id = ?", user_id)

        return render_template("sell.html", symbols=[row['symbol'] for row in rows])


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():

    user_id = session.get("user_id")

    if request.method == "POST":

        password_c = request.form.get("current_password")
        if not password_c:
            return apology("must provide username")

        password_n = request.form.get("new_password")
        if not password_n:
            return apology("must provide password")

        check = request.form.get("check")
        if check != password_n:
            return apology("Check your input and try again!")

        rows = db.execute(
            "SELECT * FROM users WHERE id = ?", user_id
        )

        hashed_password_c = generate_password_hash(password_c)

        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], hashed_password_c
        ):
            return apology("invalid password")

        hashed_password_n = generate_password_hash(password_n)

        db.execute("UPDATE users SET hash = ? WHERE id = ?", hashed_password_n, user_id)

        return redirect("/index")

    else:
        return render_template("change.html")

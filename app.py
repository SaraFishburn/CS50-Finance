import os
from decouple import config
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
# if not os.environ.get("API_KEY"):
if not config("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # User reached route via GET (as by navigating to page via link/URL)
    return render_template("index.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # Ensure value was submitted in symbol field
        if not symbol:
            return apology("invalid symbol", 403)
        # Ensure value was submitted in shares field
        elif not shares:
            return apology("missing shares", 403)

        stock = lookup(symbol)

        # Ensure symbol exists
        if not stock:
            return apology("invalid symbol", 403)

        user_id = session.get('user_id')
        user_balance = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                    user_id=user_id)[0].get('cash')
        price = stock.get('price')
        cost = price*shares
        
        # Ensure user has sufficient funds
        if user_balance < cost:
            return apology("insufficient funds", 403)
        
        else:
            return buy_sell(stock, shares, user_id, user_balance)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
    """Get stock quote."""
    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

     # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was confirmed
        elif not request.form.get("confirm-password"):
            return apology("must provide password", 403)

        # Ensure password and confirm password fields match
        elif request.form.get("password") != request.form.get("confirm-password"):
            return apology("password confirmation must match password", 403)

        # Query database for username and if available show error else create new row in db
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        
        # Check username in database
        if len(rows) != 0:
            return apology("Username already exists", 403)

        # Add row to db with new user information
        db.execute("INSERT INTO users (username, hash, cash) VALUES (:username, :hash, :cash)",
                    username=request.form.get('username'),
                    hash=generate_password_hash(request.form.get('password')),
                    cash=10000)

    # User reached route via GET (as by navigating to page via link/URL)
    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# Function to update db to reflect sale/purchase of stock
def buy_sell(stock, shares, user_id, user_balance):
    name = stock.get('name')
    price = stock.get('price')
    symbol = stock.get('symbol')
    cost = price*shares

    # Update user's cash balance
    updated_balance = user_balance - cost
    db.execute("UPDATE users SET cash = :updated_balance WHERE id = :user_id",
                    updated_balance=updated_balance,
                    user_id=user_id)
    
    # Attempt to retrieve existing stock under user's id
    stock_exists = db.execute("SELECT * FROM stocks WHERE user_id = :user_id AND symbol = :symbol",
                    user_id=user_id,
                    symbol=symbol)

    # If stock exsists, update the number of shares
    if len(stock_exists) != 0:
        updated_shares = stock_exists[0].get('shares') + shares
        stock_id = stock_exists[0].get('id')

        db.execute("UPDATE stocks SET shares = :updated_shares WHERE  id = :stock_id",
                    updated_shares=updated_shares,
                    stock_id=stock_id) 

    # Otherwise create new row in db with stock info for user
    else:
        new_stock = db.execute("INSERT INTO stocks (user_id, symbol, name, shares) VALUES (:user_id, :symbol, :name, :shares)",
                    user_id=user_id,
                    symbol=symbol,
                    name=name,
                    shares=shares)
        print(new_stock)    
        stock_id = new_stock[0].get('id')

    # Update sale/purchase history
    db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)",
                user_id=user_id,
                symbol=symbol,
                shares=shares,
                price=price)

    if stock_exists[0].get('shares') == 0:
        db.execute("DELETE FROM stock WHERE id = :stock_id AND user_id = :user_id",
                    stock_id=stock_id,
                    user_id=user_id)
                    
    return redirect("/")


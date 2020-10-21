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
    
    # Retrieve stocks user owns
    user_id = session.get('user_id')
    index_shares = db.execute("SELECT * FROM stocks WHERE user_id = :user_id",
                                user_id=user_id)

    sum_prices = 0

    # Add price and total as keys in resulting dictionary
    for row in index_shares:
        stock = lookup(row.get('symbol'))
        price = stock.get('price')
        total = price * row.get('shares')

        row['price'] = usd(price)
        row['total'] = usd(total)
        sum_prices += total

    # Retrieve user's current cash
    user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                user_id=user_id)[0].get('cash')
    cash = usd(user_cash)

    # Total of all stocks and current cash
    grand_total = usd(sum_prices + user_cash)     
        
    return render_template("index.html", 
                            cash=cash, 
                            grand_total=grand_total,
                            index_shares=index_shares)

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
        cost = price * shares
        
        # Ensure user has sufficient funds
        if user_balance < cost:
            return apology("insufficient funds", 403)
        
        else:
            flash("Bought!")
            return buy_sell(stock, shares, user_id, user_balance)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    # Retrieve rows from history relating to current user
    user_id = session.get('user_id')
    history = db.execute("SELECT * FROM history WHERE user_id = :user_id",
                            user_id=user_id)

    # Convert price to usd formatting
    for row in history:
        price = row['price']
        row['price'] = usd(price)
    
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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        

        flash("Successfully logged in!")

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

@app.route("/account")
def account():
    """User account information"""
    user_id = session.get('user_id')
    username = db.execute("SELECT username FROM users WHERE id = :user_id",
                            user_id=user_id)[0].get('username')
    return render_template("account.html", username=username)

@app.route("/change-password", methods=["GET", "POST"])
def update_password():
    """Update uder password"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure current password was submitted
        if not request.form.get("current-password"):
            return apology("must provide current password", 403)

        # Ensure new password was submitted
        elif not request.form.get("new-password"):
            return apology("must provide new password", 403)

        # Ensure new password was confirmed
        elif not request.form.get("confirm-new-password"):
            return apology("must confirm new password", 403)

        # Ensure new password and confirm new password fields match
        elif request.form.get("new-password") != request.form.get("confirm-new-password"):
            return apology("new password confirmation must match new password", 403)

        user_id = session.get('user_id')
        user_hash = db.execute("SELECT hash FROM users WHERE id = :user_id",
                                user_id=user_id)[0].get('hash')

        # Ensure current password is correct  
        if not check_password_hash(user_hash, request.form.get("current-password")):
            return apology("current password incorrect", 403)
        
        updated_password = generate_password_hash(request.form.get('new-password'))

        # Update password hash in database
        db.execute("UPDATE users SET hash = :updated_password WHERE id = :user_id",
                    updated_password=updated_password,
                    user_id=user_id)
        
        flash("Password successfully updated!")
        return redirect("/")

    # User reached route via GET (as by navigating to page via link/URL)
    else:
        return render_template("change-password.html")

@app.route("/deposit-or-withdraw", methods=["GET", "POST"])
def deposit_withdraw():
    """Add or subtract user cash"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        action = request.form.get('action')
        amount = int(request.form.get('amount'))

        # Ensure action has been selected
        if not action:
            return apology("missing action", 403)

        # Ensure amount has been entered
        elif not amount:
            return apology("missing amount", 403)
        
        # Add amount to cash if user is depositing
        elif action == 'deposit':
            return update_cash(amount)

        # Subtract amount from cash if user is withdrawing
        elif action == 'withdraw':
            amount *= -1
            return update_cash(amount)

    # User reached route via GET (as by navigating to page via link/URL)
    else:
        return render_template("deposit-or-withdraw.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        symbol = request.form.get("symbol")

        # Ensure value was submitted in symbol field
        if not symbol:
            return apology("invalid symbol", 403)

        stock = lookup(symbol)

        # Ensure symbol exists
        if not stock:
            return apology("invalid symbol", 403)

        name = stock.get("name")
        symbol = stock.get("symbol")
        price = usd(stock.get("price"))

        # Format message with stock informtation
        message = 'A share of {name} ({symbol}) costs {price}.'.format(name = name, symbol = symbol, price = price)

        return render_template("quote-message.html", message=message)
     
    else:
        return render_template("quote-form.html")

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

    user_id = session.get('user_id')

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Retrieve user's current cash balance
        user_balance = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                        user_id=user_id)[0].get('cash')

        symbol = request.form.get('symbol')
        stock = lookup(symbol)
        shares = int(request.form.get("shares")) * -1

        # Ensure value was submitted in symbol field
        if not symbol:
            return apology("missing symbol", 403)
            
        # Ensure value was submitted in shares field
        elif not shares:
            return apology("missing shares", 403)
        
        shares *= -1
        # Ensure user is unable to sell more shares than they own
        if shares > db.execute("SELECT shares FROM stocks WHERE symbol = :symbol AND user_id = :user_id",
                                    symbol=symbol,
                                    user_id=user_id)[0].get('shares'):
            return apology("too many shares", 400)

        
        flash("Sold!")

        return buy_sell(stock, shares, user_id, user_balance)

    # User reached route via GET (as by navigating to page via link/URL)
    else:
        # Retrieve list of stocks user owns
        user_symbols = db.execute("SELECT symbol FROM stocks WHERE user_id = :user_id",
                                    user_id=user_id)
        available_symbols = []
        for row in user_symbols:
            available_symbols.append(row.get('symbol'))

        return render_template("sell.html", available_symbols=available_symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# Update cash amount
def update_cash(amount):
    user_id = session.get('user_id')
    current_balance = db.execute("SELECT cash FROM users WHERE id = :user_id", 
                                user_id=user_id)[0].get('cash')

    if amount * -1 > current_balance:
        return apology("you are too poor :(", 402)

    updated_cash = current_balance + amount

    db.execute("UPDATE users SET cash = :updated_cash WHERE id = :user_id",
                updated_cash=updated_cash,
                user_id=user_id)
    return redirect("/")




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

        if updated_shares == 0:
            db.execute("DELETE FROM stock WHERE id = :stock_id AND user_id = :user_id",
                        stock_id=stock_id,
                        user_id=user_id)

    # Otherwise create new row in db with stock info for user
    else:
        stock_id = db.execute("INSERT INTO stocks (user_id, symbol, name, shares) VALUES (:user_id, :symbol, :name, :shares)",
                    user_id=user_id,
                    symbol=symbol,
                    name=name,
                    shares=shares)

    # Update sale/purchase history
    db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)",
                user_id=user_id,
                symbol=symbol,
                shares=shares,
                price=price)

                    
    return redirect("/")


from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User, db
import yfinance as yf
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

# initial
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# create database
with app.app_context():
    db.create_all()

def get_stock_data(tickers, period="1d", interval="1m"):
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            if not hist.empty:
                latest_price = hist["Close"].iloc[-1]
                data[ticker] = {
                    "price": round(latest_price, 2),
                    "currency": stock.info.get("currency", "USD"),
                    "name": stock.info.get("shortName", ticker),
                }
            else:
                data[ticker] = {"error": "No data available"}
        except Exception as e:
            data[ticker] = {"error": str(e)}
    return data

# load user
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# index
@app.route('/')
def index():
    stock_data = get_stock_data(DEFAULT_TICKERS)
    return render_template("index.html", stock_data=stock_data)

# search
@app.route('/search', methods=['GET'])
def search_stock():
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return redirect(url_for('index'))

    stock_data = get_stock_data([ticker])
    return render_template("index.html", stock_data=stock_data, searched_ticker=ticker)


# login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')


# register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')


# Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


# logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

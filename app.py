import time
import random
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User, db
import yfinance as yf
import pandas as pd


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300


# initial
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
cache = Cache(app)

# create database
with app.app_context():
    db.create_all()


@cache.memoize(timeout=300)
def get_core_data():

    core_tickers = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "^DJI", "^IXIC", "^GSPC"]

    # 1 API request
    data = yf.download(
        tickers=core_tickers,
        period="1d",
        interval="1m",
        group_by="ticker",
        progress=False,
        auto_adjust=False
    )

    # Data
    processed_data = {}
    for ticker in core_tickers:
        try:
            df = data[ticker]
            latest = df.iloc[-1]
            processed_data[ticker] = {
                "price": round(latest["Close"], 2),
                "change": round(latest["Close"] - df.iloc[0]["Open"], 2)
            }
            # delay
            time.sleep(random.uniform(1, 2))
        except KeyError:
            processed_data[ticker] = {"error": "数据暂不可用"}
    return processed_data


def get_stock_data(tickers, period="1d", interval="1m"):
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)

            if not hist.empty:
                # 计算价格变化
                price_change = round(hist["Close"].iloc[-1] - hist["Open"].iloc[0], 2)
                percent_change = round((price_change / hist["Open"].iloc[0]) * 100, 2)

                data[ticker] = {
                    "price": round(hist["Close"].iloc[-1], 2),
                    "change": percent_change,  # 添加变化百分比
                    "currency": stock.info.get("currency", "USD"),
                    "name": stock.info.get("shortName", ticker)
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

# get news
@cache.memoize(timeout=1800)

def get_news(tickers=["AAPL", "TSLA"], max_news=5):
    news_list = [{
                "title": "Market Update: Stocks Show Mixed Trends",
                "link": "#",
                "publisher": "SimplyStocks",
                "timestamp": 0
            }]
    return news_list[:max_news]


# def get_news(tickers=["AAPL", "TSLA"], max_news=5):
#     news_list = []
#     try:
#         for ticker in tickers:
#             stock = yf.Ticker(ticker)
#             news = stock.news or []
#
#             for item in news[:max_news]:
#                 # 添加更严格的字段验证
#                 if not isinstance(item, dict):
#                     continue
#
#                 # 增强默认值处理
#                 safe_item = {
#                     "title": item.get("title") or "Latest Market News",
#                     "link": item.get("link") or "#",
#                     "publisher": item.get("publisher") or "Financial News",
#                     "timestamp": item.get("providerPublishTime") or 0
#                 }
#
#                 # 添加链接有效性检查
#                 if safe_item["link"] == "#" and safe_item["title"] == "Latest Market News":
#                     continue  # 跳过无效条目
#
#                 if not any(n["link"] == safe_item["link"] for n in news_list):
#                     news_list.append(safe_item)
#
#                 if len(news_list) >= max_news:
#                     break
#
#         news_list.sort(key=lambda x: x["timestamp"], reverse=True)
#
#         # 保证至少返回示例新闻
#         if not news_list:
#             return [{
#                 "title": "Market Update: Stocks Show Mixed Trends",
#                 "link": "#",
#                 "publisher": "SimplyStocks",
#                 "timestamp": 0
#             }]
#
#     except Exception as e:
#         print(f"News Error: {str(e)}")
#
#     return news_list[:max_news]


@app.route('/')
def index():

    core_data = get_core_data()

    # divide news and data
    stock_tickers = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    index_tickers = {"^DJI": "DJI", "^IXIC": "IXIC", "^GSPC": "^GSPC"}

    stock_data = {ticker: core_data.get(ticker) for ticker in stock_tickers}
    market_indices = {name: core_data.get(ticker) for ticker, name in index_tickers.items()}

    # dews
    news = get_news()

    return render_template(
        "index.html",
        stock_data=stock_data,
        market_indices=market_indices,
        news=news
    )

# search
@app.route('/search', methods=['GET'])
def search_stock():
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return redirect(url_for('index'))

    # 获取搜索股票数据
    stock_data = get_stock_data([ticker])

    # 获取其他必要数据（复用缓存）
    core_data = get_core_data()
    index_tickers = {"^DJI": "Dow Jones", "^IXIC": "NASDAQ", "^GSPC": "S&P 500"}
    market_indices = {name: core_data.get(ticker) for ticker, name in index_tickers.items()}
    news = get_news()

    return render_template(
        "index.html",
        stock_data=stock_data,
        market_indices=market_indices,
        news=news,
        searched_ticker=ticker
    )


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

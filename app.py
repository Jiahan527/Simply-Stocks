import logging
import time
import os
import random
import re
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User, db, Portfolio
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv
from flask_talisman import Talisman


cache = Cache()
login_manager = LoginManager()


def create_app():
    load_dotenv()
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MYSQL_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    db.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)
    Talisman(app, content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "https://cdn.jsdelivr.net"],
        'style-src': ["'self'", "https://cdn.jsdelivr.net", "'unsafe-inline'"],
        'font-src': ["'self'", "https://cdn.jsdelivr.net"],
        'img-src': ["'self'", "data:", "https://*.yahoo.com"]
    })

    with app.app_context():
        db.create_all()
        register_routes(app)

    return app


def is_valid_ticker(ticker):
    return re.match(r'^[A-Z0-9]{1,10}$', ticker) is not None

def register_routes(app):
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
                processed_data[ticker] = {"error": "data error"}
        return processed_data


    @cache.memoize(timeout=60)
    def get_stock_data(tickers, period="1d", interval="1m"):
        data = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period=period, interval=interval)

                if not hist.empty:
                    price_change = round(hist["Close"].iloc[-1] - hist["Open"].iloc[0], 2)
                    percent_change = round((price_change / hist["Open"].iloc[0]) * 100, 2)

                    data[ticker] = {
                        "price": round(hist["Close"].iloc[-1], 2),
                        "change": percent_change,
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
        user_stock_data = {}
        default_stock_data = {}

        market_indices = {name: core_data.get(ticker) for ticker, name in index_tickers.items()}

        if current_user.is_authenticated:
            user_tickers = [entry.ticker for entry in current_user.portfolios]
            user_stock_data = get_stock_data(user_tickers)
            remaining_tickers = [ticker for ticker in stock_tickers if ticker not in user_tickers]
            default_stock_data = get_stock_data(remaining_tickers)
        else:
            default_stock_data = get_stock_data(stock_tickers)

        news = get_news()

        return render_template(
            "index.html",
            user_stock_data=user_stock_data,
            default_stock_data=default_stock_data,
            market_indices=market_indices,
            news=news
        )

    # search
    @app.route('/search', methods=['GET'])
    def search_stock():
        try:
            raw_ticker = request.args.get('ticker', '').strip().upper()
            if not raw_ticker:
                flash("Please enter a stock symbol.")
                return redirect(url_for('index'))

            if not is_valid_ticker(raw_ticker):
                logging.warning(f"Invalid ticker attempt: {raw_ticker}")
                flash("Invalid symbol. Only letters and numbers allowed (1-10 characters).", "danger")
                return redirect(url_for('index'))

            stock_data = get_stock_data([raw_ticker])


            core_data = get_core_data()
            index_tickers = {"^DJI": "Dow Jones", "^IXIC": "NASDAQ", "^GSPC": "S&P 500"}
            market_indices = {name: core_data.get(ticker) for ticker, name in index_tickers.items()}
            news = get_news()

            return render_template(
                "index.html",
                stock_data=stock_data,
                market_indices=market_indices,
                news=news,
                searched_ticker=raw_ticker
            )
        except Exception as e:
            logging.error(f"Search error: {str(e)}", exc_info=True)
            flash("An error occurred during the search. Please try again.")
            return redirect(url_for('index'))

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
            flash('Registration successful. Please login.', 'success')
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

    # index
    @app.route('/index')
    def back_from_dashboard_to_index():
        return redirect(url_for('index'))


    @app.route('/add_to_portfolio', methods=['POST'])
    @login_required
    def add_to_portfolio():
        ticker = request.form.get('ticker').upper().strip()

        if not yf.Ticker(ticker).info:
            flash(f"Valid Stock Code: {ticker}", "danger")
            return redirect(url_for('dashboard'))

        existing = Portfolio.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        if existing:
            flash(f"{ticker} Already in Your Portfolio List", "warning")
            return redirect(url_for('dashboard'))

        new_entry = Portfolio(user_id=current_user.id, ticker=ticker)
        db.session.add(new_entry)
        db.session.commit()
        flash(f"{ticker} has been added in Your List", "success")
        return redirect(url_for('dashboard'))



    @app.route('/remove_from_portfolio/<int:portfolio_id>', methods=['POST'])
    @login_required
    def remove_from_portfolio(portfolio_id):
        entry = Portfolio.query.get_or_404(portfolio_id)
        if entry.user_id != current_user.id:
            abort(403)
        db.session.delete(entry)
        db.session.commit()
        flash("Stock has been moved", "success")
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

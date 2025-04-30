import logging
import time
import os
import random
import re
import yfinance as yf
import pandas as pd

from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_talisman import Talisman
from dotenv import load_dotenv

from models import User, db, Portfolio

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
            data = yf.download(
                tickers=core_tickers,
                period="1d",
                interval="1m",
                group_by="ticker",
                progress=False,
                auto_adjust=False
            )

            processed_data = {}
            for ticker in core_tickers:
                try:
                    df = data[ticker]
                    latest = df.iloc[-1]
                    processed_data[ticker] = {
                        "price": round(latest["Close"], 2),
                        "change": round(latest["Close"] - df.iloc[0]["Open"], 2)
                    }
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

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        @cache.memoize(timeout=1800)
        def get_news(tickers=["AAPL", "TSLA"], max_news=5):
            return [{
                "title": "Market Update: Stocks Show Mixed Trends",
                "link": "#",
                "publisher": "SimplyStocks",
                "timestamp": 0
            }][:max_news]

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

        @app.route('/dashboard')
        @login_required
        def dashboard():
            return render_template('dashboard.html', user=current_user)

        @app.route('/logout')
        @login_required
        def logout():
            logout_user()
            return redirect(url_for('index'))

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

        @app.route('/company', methods=['POST'])
        def get_company_info():
            ticker = request.form.get('ticker', '').upper().strip()
            if not ticker:
                return "Error: No ticker provided", 400

            company = yf.Ticker(ticker)
            income_stmt = company.income_stmt.fillna("").to_dict()
            balance_sheet = company.balance_sheet.fillna("").to_dict()
            cashflow_stmt = company.cashflow.fillna("").to_dict()
            tenk_data = company.financials.fillna("").to_dict()

            return render_template("financials.html", ticker=ticker, income_statement=income_stmt, balance_sheet=balance_sheet, cashflow_statement=cashflow_stmt, tenk_data=tenk_data)

        @app.route('/api/stock-price/<ticker>')
        def get_stock_price(ticker):
            range_option = request.args.get("range", "1d")
            interval_map = {"1d": "1m", "6mo": "1d", "1y": "1d", "2y": "1d"}
            interval = interval_map.get(range_option, "1d")

            try:
                stock = yf.Ticker(ticker.upper())
                hist = stock.history(period=range_option, interval=interval)
                data = {
                    "times": hist.index.strftime("%Y-%m-%d" if interval != "1m" else "%H:%M").tolist(),
                    "prices": hist["Close"].fillna("").tolist()
                }
                return jsonify(data)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

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

        @app.route('/analysis', methods=['GET', 'POST'])
        def analysis():
            if request.method == 'POST':
                ticker = request.form.get('ticker', '').upper().strip()
                if not ticker:
                    return "Ticker required", 400

                stock = yf.Ticker(ticker)
                info = stock.info
                name = info.get("longName", ticker)
                price = info.get("currentPrice")
                change = info.get("regularMarketChangePercent")
                pe = info.get("trailingPE")
                eps = info.get("trailingEps")
                dividend = info.get("dividendRate")
                growth_rate = info.get("earningsGrowth") or 0.05

                lynch_value = round(eps * growth_rate * 22.5, 2) if eps and eps > 0 else None
                ddm_value = round(dividend / (0.08 - 0.05), 2) if dividend else None

                dcf_value = None
                fcf = info.get("freeCashflow")
                if fcf and fcf > 0:
                    discount_rate = 0.08
                    growth_rate = 0.05
                    years = 5
                    fcfs = [fcf * ((1 + growth_rate) ** year) / ((1 + discount_rate) ** year) for year in range(1, years + 1)]
                    terminal_value = (fcfs[-1] * (1 + growth_rate)) / (discount_rate - growth_rate)
                    discounted_tv = terminal_value / ((1 + discount_rate) ** years)
                    dcf_value = round(sum(fcfs) + discounted_tv, 2)

                return render_template(
                    'analysis.html', ticker=ticker, name=name, price=price, change=change,
                    pe=pe, eps=eps, growth_rate=growth_rate, dividend=dividend,
                    lynch_value=lynch_value, ddm_value=ddm_value, dcf_value=dcf_value
                )

            return render_template('analysis.html')



if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

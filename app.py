import json
import os
from datetime import time, datetime
from flask import Flask, request, render_template, redirect, send_file
import yfinance as yf
import sqlite3
import pandas as pd
import jinja2
pd.options.plotting.backend = "plotly"
import plotly
import csv
import numpy as np
import plotly.graph_objs as go
import plotly.io as pio
import ipython_genutils
import nbformat
import plotly.express as px

app = Flask(__name__)

# Get the information from yfinance for the entered stock

def get_info(ticker):
    stock = yf.Ticker(ticker)
    return(stock.info)

# Get the specified statistic the user chose
def get_statistic(info, statistic):
    if statistic == 'price':
        statistic = 'regularMarketPrice'

    if (info['exchange'] == "LSE"):
        currency = '£'
    else:
        currency = '$'
    if (statistic == "dividendYield"):
        formatted = "{:.2%}".format(info[statistic])
    elif (statistic == "regularMarketPrice" or statistic == "lastDividendValue" or statistic == "bid"):
        formatted = currency + '{:,.2f}'.format(info[statistic])
    elif (statistic == "exDividendDate"):
        formatted = datetime.utcfromtimestamp(info[statistic]).strftime('%Y-%m-%d')
    else:
        formatted = info[statistic]
    return str(formatted)

def create_db():
    conn = sqlite3.connect('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db')
    conn.execute('''CREATE TABLE PORTFOLIO
             (TRANSACTION_ID INTEGER PRIMARY KEY AUTOINCREMENT,
             INPUT_DATE TEXT NOT NULL,
             TICKER           TEXT    NOT NULL,
             SHARES            INT     NOT NULL,
             PRICE        FLOAT NOT NULL);''')
    conn.close()

def add_stock(input_date, ticker, shares, price):
    conn = sqlite3.connect('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db')
    add_entry = ("INSERT INTO PORTFOLIO (INPUT_DATE,TICKER,SHARES,PRICE) \
          VALUES (?, ?, ?, ? )");
    conn.execute(add_entry, (input_date, ticker, shares, price))
    conn.commit()
    conn.close()

def get_stocks():
    conn = sqlite3.connect('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db')
    cursor = conn.execute("SELECT TRANSACTION_ID, INPUT_DATE, TICKER, SHARES, PRICE from PORTFOLIO")
    transaction_id_array = []
    input_date_array = []
    ticker_array = []
    shares_array = []
    price_array = []
    for row in cursor:
        transaction_id_array.append(row[0])
        input_date_array.append(row[1])
        ticker_array.append(row[2])
        shares_array.append(row[3])
        price_array.append(row[4])

    conn.close()
    return transaction_id_array, input_date_array, ticker_array, shares_array, price_array

def get_other_info(prices, tickers, shares):
    current_prices = []
    unrealized_gains_dollar= []
    unrealized_gains_percent = []
    dividend_yields_on_costs = []
    portfolio_compositions = []

    total_portfolio = 0
    for y in range(len(prices)):
        stock_info = get_info(tickers[y])
        total_portfolio = total_portfolio + (float(stock_info['regularMarketPrice'])*shares[y])

    print("The TOTAL AMOUNT IN PORT IS: " + str(total_portfolio))
    for x in range(len(prices)):
        ticker = tickers[x]
        stock_info = get_info(ticker)
        current_price = float(stock_info['regularMarketPrice'])

        bought_cost = prices[x]*shares[x]
        current_cost = current_price*shares[x]
        unrealized_gain_dollar = float(current_cost - bought_cost)

        portfolio_compositions.append('{:,.2f}'.format((current_cost/total_portfolio)*100))

        unrealized_gain_percent = float(((current_cost/bought_cost) - 1)*100)

        if stock_info['dividendYield'] == None:
            dividend_yield_on_cost = 0.00
        else:
            current_dividend = float(stock_info['dividendYield']*current_price)
            dividend_yield_on_cost = float((current_dividend/prices[x])*100)

        current_prices.append(current_price)
        unrealized_gains_dollar.append('{:,.2f}'.format(unrealized_gain_dollar))
        unrealized_gains_percent.append('{:,.2f}'.format(unrealized_gain_percent))
        dividend_yields_on_costs.append('{:,.2f}'.format(dividend_yield_on_cost))

    return current_prices, unrealized_gains_dollar, unrealized_gains_percent, dividend_yields_on_costs, portfolio_compositions

def remove_stock(id):
    conn = sqlite3.connect('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db')
    delete_entry = ("DELETE FROM PORTFOLIO WHERE TRANSACTION_ID = ?");
    conn.execute(delete_entry, (id))
    conn.commit()
    conn.close()

def modify_stock(id, input_date, ticker, shares, price):
    conn = sqlite3.connect('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db')
    modify_entry_date = ("UPDATE PORTFOLIO SET INPUT_DATE = ? WHERE TRANSACTION_ID = ?");
    modify_entry_ticker = ("UPDATE PORTFOLIO SET TICKER = ? WHERE TRANSACTION_ID = ?");
    modify_entry_shares = ("UPDATE PORTFOLIO SET SHARES = ? WHERE TRANSACTION_ID = ?");
    modify_entry_price = ("UPDATE PORTFOLIO SET PRICE = ? WHERE TRANSACTION_ID = ?");
    conn.execute(modify_entry_date, (input_date, id))
    conn.execute(modify_entry_ticker, (ticker, id))
    conn.execute(modify_entry_shares, (shares, id))
    conn.execute(modify_entry_price, (price, id))
    conn.commit()
    conn.close()


def generate_csv(ids, dates, tickers, shares, costs, current_prices, unrealized_gains_dollar,
                 unrealized_gains_percent, dividend_yields_on_costs ):
    with open('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Transaction ID", "Date of Transaction", "Stock (Ticker)", "Number of Shares",
                         "Cost Per Share", "Current Price Per Share", "Unrealized Gain ($)", "Unrealized Gain (%)",
                         "Dividend Yield on Cost (%)"])
        for x in range(len(ids)):
            writer.writerow([str(ids[x]), str(dates[x]), str(tickers[x]), str(shares[x]), "$" + str(costs[x]),
                             "$" + str(current_prices[x]), "$" + str(unrealized_gains_dollar[x]),
                             str(unrealized_gains_percent[x]) + "%", str(dividend_yields_on_costs[x]) + "%"])

def generate_plot(ticker, metric, time):
    info = yf.Ticker(ticker)
    history = info.history(period=time)
    history['Dates'] = history.index
    history = history.rename(columns={'Close': 'Price'})
    input = history[['Dates', metric]]

    data = [
        go.Line(
            x=input["Dates"],
            y=input[metric]
        )
    ]
    graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

def generate_pie_plot(tickers, current_prices):
    data = [
        go.Pie(
            labels = tickers,
            values = current_prices,
            hoverinfo='label+percent'
        )
    ]
    graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

# Stock Info Page
@app.route('/stock-info/')
def my_form_stock():
    return render_template('stock-info-home.jinja2', title="Welcome")

# Get the information entered by the user on the main page
@app.route('/stock-info/', methods=['POST'])
def my_form_stock_post():
    stock = request.form['stock'].upper()
    statistic = request.form['stat']
    return redirect('/stock-info/' + stock + '/' + statistic)

@app.route('/stock-info/<stock>/<statistic>/')
def single_stock(stock, statistic):
    info = get_info(stock)
    value = get_statistic(info, statistic)

    return render_template('stock-info-individual.jinja2', value=value, stock=stock, statistic=statistic)

@app.route('/stock-info/graphing/')
def my_form_graph():
    return render_template('stock-info-graph.jinja2', title="Welcome")

@app.route('/stock-info/graphing/', methods=['POST'])
def my_form_graph_input():
    stock = request.form['stock'].upper()
    stat = request.form['stat']
    timeframe = request.form['time']

    return redirect('/stock-info/graphing/' + stock + '/' + stat + '/' + timeframe)

@app.route('/stock-info/graphing/<stock>/<statistic>/<timeframe>/')
def single_graph(stock, statistic, timeframe):
    graph = generate_plot(stock, statistic, timeframe)
    title = (str(stock) + " " + str(statistic) + " for a time period of " + str(timeframe))
    yaxis = statistic
    return render_template('stock-info-graph-individual.jinja2', plot=graph, title=title, yaxis=yaxis)

@app.route('/portfolio-tracker/')
def portfolio_app():
    if not os.path.exists('/Users/rishishah/Desktop/Projects/investment-tracker/portfolio.db'):
        create_db()
    return render_template('portfolio-tracker-home.jinja2', title="Portfolio Tracker")

@app.route('/portfolio-tracker/add/')
def add_transaction_app():
    return render_template('portfolio-tracker-add.jinja2', title="Portfolio")

@app.route('/portfolio-tracker/remove/')
def remove_transaction_app():
    transaction_ids, dates, tickers, shares, prices = get_stocks()
    current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost, port_comp = get_other_info(prices, tickers, shares)
    total = len(dates)

    return render_template('portfolio-tracker-remove.jinja2', title="Portfolio", transaction_ids=transaction_ids, dates=dates, tickers=tickers, shares=shares,
                           prices=prices, total=total, current_prices=current_prices, unreal_gain_dollar=unreal_gain_dollar,
                           unreal_gain_pct=unreal_gain_pct, div_yield_on_cost=div_yield_on_cost, port_comp=port_comp)

@app.route('/portfolio-tracker/modify/')
def modify_transaction_app():
    transaction_ids, dates, tickers, shares, prices = get_stocks()
    current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost, port_comp = get_other_info(prices, tickers, shares)
    total = len(dates)

    return render_template('portfolio-tracker-modify.jinja2', title="Portfolio", transaction_ids=transaction_ids, dates=dates, tickers=tickers, shares=shares,
                           prices=prices, total=total, current_prices=current_prices, unreal_gain_dollar=unreal_gain_dollar,
                           unreal_gain_pct=unreal_gain_pct, div_yield_on_cost=div_yield_on_cost, port_comp=port_comp)

@app.route('/portfolio-tracker/modify/', methods=['POST'])
def modify_transaction_app_form():
    stock_to_modify = request.form['modify']
    stock = request.form['stock'].upper()
    shares = int(request.form['shares'])
    date = request.form['date']
    price = float(request.form['price'])
    modify_stock(stock_to_modify, date, stock, shares, price)
    return redirect('/portfolio-tracker/modify')

@app.route('/portfolio-tracker/remove/', methods=['POST'])
def remove_transaction_app_post():
    stock_to_remove = request.form['remove']
    transaction_ids, dates, tickers, shares, prices = get_stocks()
    remove_stock(stock_to_remove)
    current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost = get_other_info(prices, tickers, shares)
    total = len(dates)

    return redirect('/portfolio-tracker/remove')

@app.route('/portfolio-tracker/add/', methods=['POST'])
def add_transaction_app_form():
    stock = request.form['stock'].upper()
    shares = int(request.form['shares'])
    date = request.form['date']
    price = float(request.form['price'])
    add_stock(date, stock, shares, price)
    return redirect('/portfolio-tracker/add')

@app.route('/portfolio-tracker/portfolio/')
def view_portfolio_app():
    transaction_ids, dates, tickers, shares, prices = get_stocks()
    current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost, port_comp = get_other_info(prices, tickers, shares)
    generate_csv(transaction_ids, dates, tickers, shares, prices, current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost)
    total = len(dates)
    pi_chart = generate_pie_plot(tickers, port_comp)
    return render_template('portfolio-tracker-table.jinja2', title="Portfolio Compositions", transaction_ids=transaction_ids, dates=dates, tickers=tickers, shares=shares,
                           prices=prices, total=total, current_prices=current_prices, unreal_gain_dollar=unreal_gain_dollar,
                           unreal_gain_pct=unreal_gain_pct, div_yield_on_cost=div_yield_on_cost, port_comp=port_comp, plot=pi_chart)

@app.route('/portfolio-tracker/download/')
def download_portfolio_app():
    transaction_ids, dates, tickers, shares, prices = get_stocks()
    current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost = get_other_info(prices, tickers, shares)
    generate_csv(transaction_ids, dates, tickers, shares, prices, current_prices, unreal_gain_dollar, unreal_gain_pct, div_yield_on_cost)
    return send_file('portfolio.csv', as_attachment=True)

@app.route('/')
def my_app():
    return render_template('home.jinja2', title="Welcome")




if __name__ == "__main__":
    app.debug = True
    app.run()


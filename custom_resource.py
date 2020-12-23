import pandas as pd
import backtrader as bt
from datetime import timedelta
from multiprocessing import Pool
from functools import partial
import random
import secrets

from backtrader_plotting import Bokeh
from backtrader_plotting.schemes import Tradimo, Blackly
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import file_html

import os

class CommInfoFractional(bt.CommissionInfo):
    
    def getsize(self, price, cash):
        '''Returns fractional size for cash operation @price'''
        return self.p.leverage * (cash / price)
    
def perform_backtest(params, df, strategy, PandasData_Custom, bokeh=False):

    curr_result = {}
    curr_result = params
    
    data = PandasData_Custom(dataname=df)
    cerebro = bt.Cerebro()

    cerebro.adddata(data)
    cerebro.addstrategy(strategy, parameters=params)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, riskfreerate=0.0, annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.Calmar)
    cerebro.addanalyzer(bt.analyzers.DrawDown)
    cerebro.addanalyzer(bt.analyzers.Returns)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer)

    initial_cash = 1000
    cerebro.broker = bt.brokers.BackBroker(cash=initial_cash, slip_perc=0.01/100, commission = CommInfoFractional(commission=(0.075*params['mult'])/100, mult=params['mult']), slip_open=True, slip_out=True)  # 0.5%

    run = cerebro.run()

    all_logs = run[0].get_logs()
    portfolio = all_logs[0] 
    trades = all_logs[1] 
    operations = all_logs[2]
    
    trades_analysis = trades.merge(operations, on='Date', how='left')
    trades_analysis = trades_analysis.fillna(method='bfill')
    trades_analysis['Date'] = pd.to_datetime(trades_analysis['Date'])
    trades_analysis['Date'] = trades_analysis['Date'] - timedelta(minutes=10)

    analysis = run[0].analyzers.getbyname('tradeanalyzer').get_analysis()
    
    try:
        curr_result['Total Trades'] = analysis['total']['total']
    except:
        curr_result['Total Trades'] = 0
    
    try:
        curr_result['Total Profit'] = analysis['won']['total']
        curr_result['Avg Profit'] = analysis['won']['pnl']['average']
    except:
        curr_result['Total Profit'] = 0
        curr_result['Avg Profit'] = 0
        
    try:
        curr_result['Total Loss'] = analysis['lost']['total']
        curr_result['Average Loss'] = analysis['lost']['pnl']['average']
    except:
        curr_result['Total Loss'] = 0
        curr_result['Average Loss'] = 0
        
    try:
        curr_result['Total Long'] = analysis['long']['total']
        curr_result['Average Long'] = analysis['long']['pnl']['average']
    except:
        curr_result['Total Long'] = 0
        curr_result['Average Long'] = 0
        
    try:
        curr_result['Total Short'] = analysis['short']['total']
        curr_result['Average Short'] = analysis['short']['pnl']['average']
    except:
        curr_result['Total Short'] = 0
        curr_result['Average Short'] = 0
    
    curr_result['Return (%)'] = round(((portfolio['Value'].iloc[-1] - portfolio['Value'].iloc[0])/portfolio['Value'].iloc[0]) * 100, 2)
    curr_result['sharpe'] = run[0].analyzers.getbyname('sharperatio').get_analysis()['sharperatio']
    
    portfolio['Date'] = pd.to_datetime(portfolio['Date'])
    portfolio = portfolio.set_index('Date')

    daily_portfolio = portfolio.resample('1D').agg({'Value': lambda x: x.iloc[-1]})
    
    if bokeh == True:
        b = Bokeh(style='bar', plot_mode='single', scheme=Tradimo())
        fig = cerebro.plot(b)

        s_fig = fig[0][0]

        bokeh_html = file_html(s_fig.model, CDN, "Backtest Plot")
        
        if not os.path.isdir("bokeh/"):
            os.makedirs("bokeh/")
            
        fname = secrets.token_hex(3) + ".html"
            
        with open('bokeh/{}'.format(fname), 'w') as file:
            file.write(bokeh_html)
            
        return fname
        
    return curr_result


def get_random_pars(all_params):
    random_param = {}

    for idx, val in all_params.items():
        random_param[idx] = random.choice(val)
    
    return random_param
    
def perform_grid_search(curr_df, all_params, strategy, PandasData_Custom, iterations=600):
    lst = list(all_params.keys())    
    df = curr_df
    grid = pd.DataFrame()         

    at_once = 16
    p = Pool(at_once)
    count = 0

    for i in range(iterations//at_once):
        if i % 5 == 0:
            print(i*at_once)
            
        selected = [get_random_pars(all_params) for x in range(at_once)]
                
        for ser in p.imap_unordered(partial(perform_backtest, df=df, strategy=strategy, PandasData_Custom=PandasData_Custom), selected):      
            res = pd.Series(ser)
            grid = grid.append(pd.Series(ser), ignore_index=True)
            count = count + 1


    grid['win_percentage'] = grid['Total Profit']/grid['Total Trades']
    grid = grid[grid['Return (%)'] != 0]

    grid = grid.sort_values('Return (%)', ascending=False)[['Return (%)', 'sharpe'] + lst +  ['Total Trades', 'Total Profit', 'win_percentage']][:60]

    return grid
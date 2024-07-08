import os
import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import plotly.express as px
import plotly.graph_objects as go

# Function to read tickers from the CSV file
def get_listed_companies_from_csv(file_path):
    companies = pd.read_csv(file_path, skiprows=1)
    tickers = companies['Code'].dropna().tolist()  # Ensure no empty tickers are included
    return tickers

# Function to get stock data
def get_stock_data(ticker, start_date, end_date):
    stock_data = yf.download(ticker, start=start_date, end=end_date)
    if 'Adj Close' in stock_data.columns:
        stock_data['Close'] = stock_data['Adj Close']
    stock_data['50_MA'] = stock_data['Close'].rolling(window=50).mean()
    stock_data['200_MA'] = stock_data['Close'].rolling(window=200).mean()
    return stock_data

# Function to calculate recovery times
def calculate_recovery_times(stock_data):
    stock_data['Drawdown'] = (stock_data['50_MA'] < stock_data['200_MA']).astype(int)
    stock_data['Recovery'] = (stock_data['50_MA'] >= stock_data['200_MA']).astype(int)
    
    drawdown_start_indices = stock_data.index[stock_data['Drawdown'].diff() == 1]
    recovery_start_indices = stock_data.index[stock_data['Recovery'].diff() == 1]

    recoveries = []
    for drawdown_start in drawdown_start_indices:
        recovery_start_candidates = recovery_start_indices[recovery_start_indices > drawdown_start]
        if not recovery_start_candidates.empty:
            recovery_start = recovery_start_candidates[0]
            recoveries.append((drawdown_start, recovery_start, (recovery_start - drawdown_start).days))
    
    return recoveries

# Prompt user for input
analysis_choice = input("Do you want to run the analysis on all stocks or just the top 50? Enter 'all' or 'top50': ").strip().lower()

# Define the period for historical data
start_date = '2010-01-01'
end_date = dt.datetime.today().strftime('%Y-%m-%d')

# Create a DataFrame to store recovery times
recovery_times_list = []

# Valid tickers list
valid_tickers = []

best_50_stocks_csv = 'best_50_stocks.csv'
all_asx_tickers_csv = 'all_asx_tickers.csv'
recovery_times_csv = 'recovery_times.csv'

# Check if the CSV for all ASX tickers already exists
if analysis_choice == 'all' and os.path.exists(all_asx_tickers_csv) and os.path.exists(recovery_times_csv):
    all_asx_tickers = pd.read_csv(all_asx_tickers_csv)
    print("All ASX tickers loaded from existing CSV.")
    list_of_tickers = all_asx_tickers['Ticker'].tolist()
    recovery_times_df = pd.read_csv(recovery_times_csv)
elif analysis_choice == 'top50' and os.path.exists(best_50_stocks_csv) and os.path.exists(recovery_times_csv):
    best_50_stocks = pd.read_csv(best_50_stocks_csv)
    print("Best 50 stocks loaded from existing CSV.")
    list_of_tickers = best_50_stocks['Ticker'].tolist()
    recovery_times_df = pd.read_csv(recovery_times_csv)
else:
    csv_file_path = 'asx-listed-companies.csv'
    list_of_tickers = get_listed_companies_from_csv(csv_file_path)

    # Analyze each stock and calculate recovery times
    for ticker in list_of_tickers:
        try:
            stock_data = get_stock_data(ticker, start_date, end_date)
            if not stock_data.empty:
                valid_tickers.append(ticker)
                recoveries = calculate_recovery_times(stock_data)
                for drawdown_start, recovery_start, days in recoveries:
                    recovery_times_list.append({'Ticker': ticker, 'Drawdown Start': drawdown_start, 'Recovery Start': recovery_start, 'Recovery Days': days})
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    # Save valid tickers to a new CSV file
    valid_tickers_df = pd.DataFrame(valid_tickers, columns=['Ticker'])
    valid_tickers_df.to_csv(all_asx_tickers_csv, index=False)
    print("Valid ASX tickers have been written to all_asx_tickers.csv")

    # Convert the list to a DataFrame
    recovery_times_df = pd.DataFrame(recovery_times_list)

    # Calculate the average recovery time for each stock
    average_recovery_times = recovery_times_df.groupby('Ticker')['Recovery Days'].mean().reset_index()

    # Select the best 50 stocks with the shortest average recovery times
    best_50_stocks = average_recovery_times.nsmallest(50, 'Recovery Days')
    best_50_stocks.to_csv(best_50_stocks_csv, index=False)
    list_of_tickers = best_50_stocks['Ticker'].tolist()
    print("Best 50 stocks have been written to best_50_stocks.csv")
    
    # Save the recovery times list to a CSV
    recovery_times_df.to_csv(recovery_times_csv, index=False)

# Create a bubble chart with one bubble per stock representing the average recovery time
average_recovery_times = recovery_times_df.groupby('Ticker')['Recovery Days'].mean().reset_index()
fig = px.scatter(average_recovery_times, x='Ticker', y='Recovery Days', size='Recovery Days', title='Average Recovery Time for Stocks', labels={'Ticker': 'Ticker', 'Recovery Days': 'Average Recovery Time (days)'}, color='Recovery Days', color_continuous_scale=px.colors.sequential.Viridis_r)
fig.update_traces(marker=dict(line=dict(width=2, color='DarkSlateGrey')), selector=dict(mode='markers'))
fig.show()

# Fetch ASX 200 index data
asx200_data = yf.download('^AXJO', start=start_date, end=end_date)

# Plot the market index and the recovery periods of the best 50 stocks
fig_market = go.Figure()

# Add ASX 200 index trace
fig_market.add_trace(go.Scatter(x=asx200_data.index, y=asx200_data['Close'], mode='lines', name='ASX 200 Index'))

# Add recovery periods of the best 50 stocks
if 'list_of_tickers' in locals():
    for ticker in list_of_tickers:
        ticker_data = recovery_times_df[recovery_times_df['Ticker'] == ticker]
        drawdown_start_dates = [date for date in ticker_data['Drawdown Start'] if date in asx200_data.index]
        recovery_start_dates = [date for date in ticker_data['Recovery Start'] if date in asx200_data.index]
        fig_market.add_trace(go.Scatter(x=drawdown_start_dates, y=[asx200_data.loc[date]['Close'] for date in drawdown_start_dates], mode='markers+text', name=f'{ticker} Drawdown Start', text=ticker_data['Ticker'], textposition='top center', visible='legendonly'))
        fig_market.add_trace(go.Scatter(x=recovery_start_dates, y=[asx200_data.loc[date]['Close'] for date in recovery_start_dates], mode='markers+text', name=f'{ticker} Recovery Start', text=ticker_data['Ticker'], textposition='bottom center', visible='legendonly'))

# Add buttons to toggle visibility
buttons = []
for ticker in list_of_tickers:
    buttons.append(dict(method='update',
                        label=ticker,
                        args=[{'visible': [True if trace.name == 'ASX 200 Index' or ticker in trace.name else False for trace in fig_market.data]},
                              {'title': f"Market Index and Recovery Periods of {ticker}"}]))

# Add button to show all
buttons.append(dict(method='update',
                    label='All',
                    args=[{'visible': [True] * len(fig_market.data)},
                          {'title': 'Market Index and Recovery Periods of Top 50 Stocks'}]))

fig_market.update_layout(updatemenus=[dict(active=0, buttons=buttons, x=1.15, y=1.15)])
fig_market.update_layout(title='Market Index and Recovery Periods of Top 50 Stocks', xaxis_title='Date', yaxis_title='Price', legend_title='Legend')
fig_market.show()

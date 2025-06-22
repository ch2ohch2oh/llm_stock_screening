import requests
import pandas as pd
import os
import argparse
from datetime import datetime

def download_nasdaq_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Downloads daily historical stock data from nasdaq.com for a given ticker.

    Args:
        ticker (str): The stock ticker symbol (e.g., 'AAPL').
        start_date (str): The start date in 'YYYY-MM-DD' format.
        end_date (str): The end date in 'YYYY-MM-DD' format.

    Returns:
        pd.DataFrame: A DataFrame containing the historical data (Date, Close,
                      Volume, Open, High, Low), or None if an error occurs.
    """
    # Nasdaq uses a large limit to return all data in the date range in one request
    # We set a very large number to ensure we get all the data.
    limit = 99999

    # The API endpoint for historical data
    url = f"https://api.nasdaq.com/api/quote/{ticker.upper()}/historical"
    
    params = {
        "assetclass": "stocks",
        "fromdate": start_date,
        "todate": end_date,
        "limit": limit,
    }

    # Nasdaq API requires a user-agent header to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"Requesting data for {ticker} from {start_date} to {end_date}...")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        data = response.json()

        if data['data'] and data['data']['tradesTable']:
            rows = data['data']['tradesTable']['rows']
            df = pd.DataFrame(rows)

            # --- Data Cleaning and Formatting ---
            # Rename columns to a more standard format
            df = df.rename(columns={
                'date': 'Date',
                'close': 'Close',
                'volume': 'Volume',
                'open': 'Open',
                'high': 'High',
                'low': 'Low'
            })

            # Remove the dollar sign and commas, then convert to numeric types
            for col in ['Close', 'Open', 'High', 'Low']:
                df[col] = df[col].str.replace(r'[$,]', '', regex=True).astype(float)
            df['Volume'] = df['Volume'].str.replace(',', '', regex=True).astype(int)

            # Convert date column to datetime objects and format it
            df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
            
            # Reorder columns and sort by date
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].sort_values(by='Date').reset_index(drop=True)
            
            return df
        else:
            print(f"No data found for ticker {ticker} in the specified date range.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download historical stock data from Nasdaq.")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL, GOOG). Note: Nasdaq.com typically provides about 10 years of historical data.")
    parser.add_argument("--start", default=None, help="Start date in YYYY-MM-DD format. If not provided, downloads from the earliest available date.")
    parser.add_argument("--end", default=datetime.now().strftime('%Y-%m-%d'), help="End date in YYYY-MM-DD format.")
    parser.add_argument("--outdir", default="data", help="The directory to save the output CSV file. Defaults to 'data'.")
    args = parser.parse_args()

    # If no start date is provided, use a very early date to fetch all history.
    # The Nasdaq API will return data from the actual first trading day.
    start_date_for_api = args.start if args.start else "1970-01-01"

    historical_data = download_nasdaq_data(args.ticker, start_date_for_api, args.end)

    if historical_data is not None and not historical_data.empty:
        # For the output filename, use the user-provided start date,
        # or if it was not provided, use the actual earliest date from the data.
        if args.start:
            start_date_for_filename = args.start
        else:
            # Get the first date from the downloaded data and format it
            actual_start_date = historical_data['Date'].min()
            start_date_for_filename = actual_start_date.strftime('%Y-%m-%d')

        # --- File Saving ---
        # Define the output directory from the argument and create it if it doesn't exist.
        output_dir = args.outdir
        os.makedirs(output_dir, exist_ok=True)

        # Construct the filename and the full path to save the file.
        output_filename = f"{args.ticker.upper()}_{start_date_for_filename}_to_{args.end}.csv"
        output_filepath = os.path.join(output_dir, output_filename)

        historical_data.to_csv(output_filepath, index=False)
        print(f"Data successfully downloaded and saved to {output_filepath}")
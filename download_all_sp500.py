import pandas as pd
import subprocess
import sys
import os
import argparse
import time
from datetime import datetime

def download_all_tickers(csv_path: str, start_date: str | None, end_date: str):
    """
    Reads tickers from a CSV file and calls the nasdaq_downloader.py script for each one.

    Args:
        csv_path (str): The path to the CSV file containing tickers.
        start_date (str | None): The start date for the data download (YYYY-MM-DD).
        end_date (str): The end date for the data download (YYYY-MM-DD).
    """
    # Check if the CSV file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    # Read the tickers from the CSV
    try:
        df = pd.read_csv(csv_path)
        # Clean up column names by stripping leading/trailing whitespace
        df.columns = df.columns.str.strip()

        if 'Ticker' not in df.columns:
            print(f"Error: Could not find a 'Ticker' column in '{csv_path}'.")
            return
            
        tickers = df['Ticker'].dropna().unique().tolist()
    except Exception as e:
        print(f"Error reading or processing CSV file: {e}")
        return

    print(f"Found {len(tickers)} unique tickers in '{os.path.basename(csv_path)}'.")

    downloader_script = os.path.join(os.path.dirname(__file__), 'nasdaq_downloader.py')
    if not os.path.exists(downloader_script):
        print(f"Error: The downloader script 'nasdaq_downloader.py' was not found in the same directory.")
        return

    success_count = 0
    fail_count = 0

    for i, ticker in enumerate(tickers):
        print(f"\n--- [{i+1}/{len(tickers)}] Downloading data for {ticker} ---")
        
        command = [sys.executable, downloader_script, ticker]
        if start_date:
            command.extend(['--start', start_date])
        if end_date:
            command.extend(['--end', end_date])
        
        try:
            # Using check=True will raise CalledProcessError on non-zero exit codes.
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
            print(result.stdout.strip())
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"ERROR downloading {ticker}: Process failed.")
            # The nasdaq_downloader prints its own errors, so we show stderr if it exists.
            if e.stderr:
                print(f"Stderr: {e.stderr.strip()}")
            fail_count += 1
        except subprocess.TimeoutExpired:
            print(f"ERROR downloading {ticker}: The download timed out.")
            fail_count += 1
        except Exception as e:
            print(f"An unexpected error occurred for {ticker}: {e}")
            fail_count += 1
        
        # Pause for 1 second to avoid overwhelming the server
        time.sleep(1)

    print("\n--- Download Summary ---")
    print(f"Successful: {success_count}")
    print(f"Failed:     {fail_count}")
    print("------------------------")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download historical data for all tickers in a given CSV file.")
    parser.add_argument("csv_file", default="sp500.csv", nargs='?', help="Path to the CSV file containing tickers. Defaults to 'sp500.csv'.")
    parser.add_argument("--start", default=None, help="Start date in YYYY-MM-DD format. If not provided, downloads from the earliest available date.")
    parser.add_argument("--end", default=datetime.now().strftime('%Y-%m-%d'), help="End date in YYYY-MM-DD format.")
    args = parser.parse_args()

    download_all_tickers(args.csv_file, start_date=args.start, end_date=args.end)
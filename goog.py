import backtrader as bt
import datetime
import glob
import os # Added for path handling

class MomentumDrawdownStrategy(bt.Strategy):
    params = dict(
        momentum_period=30,  # ~3 months of trading days
        min_hold_days=30,
        max_drawdown=0.20,
    )
    
    def __init__(self):
        self.order = None
        self.buy_price = None
        self.buy_date = None
        self.momentum = bt.ind.PercentChange(self.data.close, period=self.p.momentum_period)
        self.highest_since_entry = None
    
    def next(self):
        if self.position.size == 0:
            # No position, check buy condition
            if self.momentum[0] is not None and self.momentum[0] > 0:
                self.order = self.buy()
                self.buy_price = self.data.close[0]
                self.buy_date = self.datas[0].datetime.date(0)
                self.highest_since_entry = self.data.close[0]
                # print(f"BUY at {self.buy_price} on {self.buy_date}")
        else:
            # Update highest price since entry for drawdown calc
            if self.data.close[0] > self.highest_since_entry:
                self.highest_since_entry = self.data.close[0]

            # Calculate drawdown since entry
            drawdown = (self.data.close[0] - self.highest_since_entry) / self.highest_since_entry
            
            # Days held
            days_held = (self.datas[0].datetime.date(0) - self.buy_date).days

            # Sell conditions only if held minimum days and price > buy_price
            if days_held >= self.p.min_hold_days and self.data.close[0] > self.buy_price:
                if self.momentum[0] < 0 or drawdown < -self.p.max_drawdown:
                    self.order = self.sell()
                    # print(f"SELL at {self.data.close[0]} on {self.datas[0].datetime.date(0)} after {days_held} days")

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # --- Data Loading from CSV File ---
    # Define the path to your local data file.
    # This assumes the CSV is in a 'data' subfolder relative to this script.
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    ticker = 'GOOG'

    # --- Find data file and parse dates from filename ---
    # Search for a file that matches the ticker pattern, e.g., GOOG_2018-06-01_to_2023-06-01.csv
    search_pattern = os.path.join(data_folder, f"{ticker.upper()}_*_to_*.csv")
    matching_files = glob.glob(search_pattern)

    if not matching_files:
        print(f"Error: No data file found for ticker '{ticker}' in folder '{data_folder}'")
        print(f"Please run 'python nasdaq_downloader.py {ticker}' and ensure the file is in the 'data' folder.")
        exit()

    # Use the first file found
    data_filepath = matching_files[0]
    if len(matching_files) > 1:
        print(f"Warning: Multiple files found for {ticker}. Using '{os.path.basename(data_filepath)}'")

    # Extract start and end dates from the filename
    try:
        filename = os.path.basename(data_filepath)
        parts = filename.replace('.csv', '').split('_') # -> ['GOOG', '2018-06-01', 'to', '2023-06-01']
        start_date_str = parts[1]
        end_date_str = parts[3]
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
    except (IndexError, ValueError):
        print(f"Error: Could not parse dates from filename '{filename}'.")
        print("Expected format: TICKER_YYYY-MM-DD_to_YYYY-MM-DD.csv")
        exit()

    print(f"Loading data for {ticker} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Create a data feed from the CSV file
    datafeed = bt.feeds.GenericCSVData(
        dataname=data_filepath,
        fromdate=start_date,
        todate=end_date,
        dtformat=('%Y-%m-%d'),
        # The CSV from nasdaq_downloader.py does not have an 'Open Interest' column.
        # We must tell backtrader to ignore it by setting the column index to -1.
        openinterest=-1)

    cerebro.adddata(datafeed)
    cerebro.addstrategy(MomentumDrawdownStrategy)

    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)  # 0.1% commission
    
    print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
    cerebro.run()
    print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')
    
    # The 'candlestick' style ensures the x-axis is formatted with dates.
    cerebro.plot(style='candlestick')

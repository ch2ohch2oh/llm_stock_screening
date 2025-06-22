import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import argparse
import os
import glob
import subprocess
import sys


def load_data(ticker: str, start_date_str: str = None, end_date_str: str = None) -> pd.DataFrame | None:
    """Finds, loads, and filters the stock data from a CSV file."""
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    search_pattern = os.path.join(data_folder, f"{ticker.upper()}_*_to_*.csv")
    matching_files = glob.glob(search_pattern)

    if not matching_files:
        print(f"No data file found for ticker '{ticker}'. Attempting to download...")
        downloader_script = os.path.join(os.path.dirname(__file__), 'nasdaq_downloader.py')
        
        command = [sys.executable, downloader_script, ticker]
        # If start/end dates are passed to the plotting script, use them for the download.
        # Otherwise, the downloader will fetch the full history by default.
        if start_date_str:
            command.extend(['--start', start_date_str])
        if end_date_str:
            command.extend(['--end', end_date_str])

        try:
            # Using check=True will raise CalledProcessError on non-zero exit codes.
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(result.stdout)
            print("Download successful. Reloading data...")
            matching_files = glob.glob(search_pattern)
            if not matching_files:
                print("Error: Data downloaded but still could not find the file.")
                return None
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Error running downloader script for {ticker}:\n{e}")
            return None

    data_filepath = matching_files[0]
    if len(matching_files) > 1:
        print(f"Warning: Multiple files found for {ticker}. Using '{os.path.basename(data_filepath)}'")

    print(f"Loading data from: {os.path.basename(data_filepath)}")

    try:
        df = pd.read_csv(data_filepath, parse_dates=['Date'], index_col='Date')
    except Exception as e:
        print(f"Error reading or parsing CSV file: {e}")
        return None

    if start_date_str or end_date_str:
        original_start = df.index.min().strftime('%Y-%m-%d')
        original_end = df.index.max().strftime('%Y-%m-%d')
        df = df.loc[start_date_str:end_date_str]
        if df.empty:
            print(f"Error: No data available for the selected range: {start_date_str or 'start'} to {end_date_str or 'end'}.")
            print(f"The full data file covers {original_start} to {original_end}.")
            return None
    return df


def calculate_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Calculates all analytical metrics and returns the updated DataFrame
    and a dictionary of key statistics for plotting.
    """
    # --- Drawdown ---
    df['Peak'] = df['Close'].cummax()
    df['Drawdown'] = (df['Close'] - df['Peak']) / df['Peak']

    # --- Rolling Returns ---
    df['Return_1Y'] = df['Close'].pct_change(periods=252)
    df['Return_2Y'] = df['Close'].pct_change(periods=504)  # Approx 252 * 2
    df['Return_3Y'] = df['Close'].pct_change(periods=252*3) # Approx 252 * 3

    # --- Key Statistics for Annotations ---
    stats = {}
    stats['max_drawdown_date'] = df['Drawdown'].idxmin()
    stats['max_drawdown_value'] = df['Drawdown'].min()
    peak_value = df.loc[stats['max_drawdown_date'], 'Peak']
    stats['peak_date'] = df[df['Close'] == peak_value].index[0]
    post_trough_df = df.loc[stats['max_drawdown_date']:]
    recovery_dates = post_trough_df[post_trough_df['Close'] >= peak_value].index
    stats['recovery_date'] = recovery_dates[0] if len(recovery_dates) > 0 else None

    return df, stats

# ==============================================================================
# --- PLOTTING FUNCTIONS ---
# Each function is responsible for drawing one subplot.
# ==============================================================================

def plot_price_chart(ax: plt.Axes, df: pd.DataFrame, stats: dict):
    """Plots the price chart with overlays."""
    ax.plot(df.index, df['Close'], label='Close Price', color='blue')
    ax.plot(df.index, df['Peak'], label='Historical Peak', color='green', linestyle='--', alpha=0.6)

    if stats['recovery_date']:
        ax.axvspan(stats['peak_date'], stats['recovery_date'], color='grey', alpha=0.2, label='Max Drawdown Period')
    else:
        ax.axvspan(stats['peak_date'], df.index[-1], color='grey', alpha=0.2, label='Max Drawdown Period (Ongoing)')

    ax.set_ylabel('Price ($)')
    ax.legend()
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

def plot_drawdown_chart(ax: plt.Axes, df: pd.DataFrame, stats: dict):
    """Plots the historical drawdown chart."""
    ax.fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.5)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel('Drawdown')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    if stats['recovery_date']:
        time_to_recover = (stats['recovery_date'] - stats['peak_date']).days
        recovery_info = f"\nTime to Recover: {time_to_recover} days"
    else:
        recovery_info = "\n(Not yet recovered)"

    annotation_text = f"Max Drawdown: {stats['max_drawdown_value']:.2%}{recovery_info}"
    ax.annotate(annotation_text,
                 xy=(stats['max_drawdown_date'], stats['max_drawdown_value']),
                 xytext=(stats['max_drawdown_date'], stats['max_drawdown_value'] * 0.5),
                 arrowprops=dict(facecolor='black'),
                 ha='center', va='top')

def plot_rolling_return_chart(ax: plt.Axes, df: pd.DataFrame, stats: dict):
    """Plots rolling returns for multiple periods."""
    ax.plot(df.index, df['Return_1Y'], label='1-Year Return', color='green', alpha=0.8)
    ax.plot(df.index, df['Return_2Y'], label='2-Year Return', color='darkorange', alpha=0.8)
    ax.plot(df.index, df['Return_3Y'], label='3-Year Return', color='royalblue', alpha=0.8)
    ax.axhline(0, color='grey', linestyle='--', linewidth=0.8)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel('Return')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend()


# ==============================================================================
# --- MAIN ORCHESTRATION ---
# ==============================================================================

def run_and_plot_analysis(ticker: str, start_date_str: str = None, end_date_str: str = None, output_path: str | None = None):
    """Main function to orchestrate data loading, analysis, and plotting."""
    df = load_data(ticker, start_date_str, end_date_str)
    if df is None:
        return

    df, stats = calculate_metrics(df)

    # --- Plotting Configuration ---
    # To add a new plot, add a new dictionary to this list.
    # 'function': The plotting function to call.
    # 'title': The title for the subplot.
    # 'height_ratio': The relative height of the subplot.
    plot_configs = [
        {'function': plot_price_chart, 'title': 'Stock Price', 'height_ratio': 3},
        {'function': plot_drawdown_chart, 'title': 'Drawdown from Peak', 'height_ratio': 1},
        {'function': plot_rolling_return_chart, 'title': 'Rolling Returns', 'height_ratio': 1},
    ]

    num_plots = len(plot_configs)
    height_ratios = [p['height_ratio'] for p in plot_configs]

    fig, axes = plt.subplots(
        num_plots, 1,
        sharex=True,
        figsize=(12, 3 * num_plots),
        gridspec_kw={'height_ratios': height_ratios}
    )
    if num_plots == 1:
        axes = [axes] # Ensure axes is always a list

    # --- Generate Plots ---
    for i, config in enumerate(plot_configs):
        ax = axes[i]
        config['function'](ax, df, stats)
        ax.set_title(config['title'])

    # --- Final Figure Formatting ---
    main_title = f'{ticker.upper()} Price and Risk Analysis'
    if start_date_str or end_date_str:
        plot_start = df.index.min().strftime('%Y-%m-%d')
        plot_end = df.index.max().strftime('%Y-%m-%d')
        main_title += f'\n({plot_start} to {plot_end})'
    fig.suptitle(main_title, fontsize=16)

    plt.xlabel('Date')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    if output_path:
        print(f"Saving plot to {output_path}...")
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, bbox_inches='tight')
        plt.close(fig)  # Close the figure to free up memory
    else:
        plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Plot the historical price and max drawdown for a stock from a local CSV file.")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., GOOG) to plot.")
    parser.add_argument("--start", help="Start date for analysis in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date for analysis in YYYY-MM-DD format.")
    parser.add_argument("--output", help="Path to save the output plot image. If not provided, the plot will be displayed interactively.")
    args = parser.parse_args()

    run_and_plot_analysis(args.ticker, start_date_str=args.start, end_date_str=args.end, output_path=args.output)
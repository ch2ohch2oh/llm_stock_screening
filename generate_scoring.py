import os
import argparse
import json
import pandas as pd
import glob
import matplotlib.pyplot as plt
from scoring import compute_stock_score
from plot_analysis import run_and_plot_analysis

def score_stocks_in_folder(data_folder: str = 'data/', min_years_history: int = 5) -> dict:
    """
    Reads all stock CSVs from a folder, computes their scores, and returns them.

    Args:
        data_folder (str): The path to the folder containing stock data CSVs.
        min_years_history (int): The minimum years of data required for a stock to be scored.

    Returns:
        dict: A dictionary mapping stock tickers to their computed scores.
    """
    scores = {}
    if not os.path.isdir(data_folder):
        print(f"Error: Data folder '{data_folder}' not found.")
        return scores

    print(f"Scoring stocks from '{os.path.abspath(data_folder)}'...")
    for filename in sorted(os.listdir(data_folder)):
        if not filename.lower().endswith('.csv'):
            continue

        ticker = filename.split('_')[0]
        filepath = os.path.join(data_folder, filename)

        try:
            df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
            required_days = min_years_history * 365.25
            if df.empty or (df.index.max() - df.index.min()).days < required_days:
                continue

            # Slice the DataFrame to only use the last 5 years of data for scoring
            end_date = df.index.max()
            start_date = end_date - pd.DateOffset(years=5)
            scoring_df = df.loc[start_date:]

            # Ensure there's still data to score after slicing
            if scoring_df.empty:
                continue

            score = compute_stock_score(scoring_df['Close'], annualization_factor=252, 
                                        ann_return_weight=1.0,
                                        max_dd_weight=-2.0,
                                        slope_to_noise_weight=4.0)
            scores[ticker] = score
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    return scores

def get_ranked_stocks(min_years: int, top_n: int) -> list[dict]:
    """
    Scores stocks by calling the scoring function directly and returns the top N.

    Args:
        min_years (int): The minimum years of history for a stock to be scored.
        top_n (int): The number of top stocks to return from the ranking.

    Returns:
        A list of dictionaries, each containing ranking, ticker, and score.
    """
    print("--- Running Stock Scoring ---")
    # Call the local scoring function
    all_scores = score_stocks_in_folder(data_folder='data', min_years_history=min_years)

    if not all_scores:
        print("Warning: No stocks were scored. Exiting.")
        return []

    # Sort the stocks by score in descending order
    sorted_scores = sorted(all_scores.items(), key=lambda item: item[1], reverse=True)

    # Get the top N stocks
    num_to_show = min(top_n, len(sorted_scores))
    top_stocks_with_scores = sorted_scores[:num_to_show]

    if not top_stocks_with_scores:
        print("No stocks to generate reports for.")
        return []

    # Print the ranking and prepare the list of (rank, ticker) tuples
    print(f"\n--- Top {num_to_show} Stocks by Score ---")
    ranked_stocks_data = []
    for rank, (ticker, score) in enumerate(top_stocks_with_scores, 1):
        print(f"{rank}. {ticker}: {score:.4f}")
        ranked_stocks_data.append({
            "ranking": rank,
            "ticker": ticker,
            "score": score
        })

    return ranked_stocks_data

def generate_analysis_plots(ranked_stocks_data: list[dict], output_dir: str):
    """
    Generates and saves analysis plots for a list of ranked stocks.
    This function modifies the dictionaries in the list in-place to add the figure path.

    Args:
        ranked_stocks_data (list[dict]): The list of ranked stock data dictionaries.
        output_dir (str): The directory where plot images will be saved.
    """
    print(f"\n--- Generating Analysis Plots in '{os.path.abspath(output_dir)}' ---")
    os.makedirs(output_dir, exist_ok=True)

    for stock_data in ranked_stocks_data:
        rank = stock_data['ranking']
        ticker = stock_data['ticker']

        print(f"[{rank}/{len(ranked_stocks_data)}] Generating plot for {ticker}...")
        # Format with leading zeros for correct file sorting (e.g., 01-AAPL.png)
        output_filename = f"{ticker}.png"
        output_filepath = os.path.join(output_dir, output_filename)
        
        try:
            # Directly call the plotting function from the other script
            run_and_plot_analysis(ticker=ticker, output_path=output_filepath)
            # Add the absolute path of the generated figure to the dictionary
            stock_data['figure'] = os.path.abspath(output_filepath)
        except Exception as e:
            print(f"  -> Error generating plot for {ticker}: {e}")
            stock_data['figure'] = None # Indicate failure

def plot_normalized_prices(top_stocks: list, data_folder: str = 'data/'):
    """
    Plots the normalized 'Close' price for a list of top-ranked stocks.

    Args:
        top_stocks (list): A list of (ticker, score) tuples.
        data_folder (str): The path to the folder containing stock data CSVs.
    """
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(15, 12))

    print(f"\n--- Plotting normalized prices for top {len(top_stocks)} stocks... ---")

    for ticker, score in top_stocks:
        search_pattern = os.path.join(data_folder, f"{ticker.upper()}_*_to_*.csv")
        matching_files = glob.glob(search_pattern)

        if not matching_files:
            print(f"Warning: Could not find data file for ticker {ticker}. Skipping plot.")
            continue

        filepath = matching_files[0]
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        normalized_price = (df['Close'] / df['Close'].iloc[0]) * 100
        ax.plot(normalized_price, label=f"{ticker} (Score: {score:.2f})", alpha=0.8)

    ax.set_title(f'Normalized Price Performance of Top {len(top_stocks)} Stocks', fontsize=16)
    ax.set_ylabel('Normalized Price (Initial Price = 100)')
    ax.set_xlabel('Date')
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), borderaxespad=0.)
    fig.tight_layout(rect=[0, 0, 0.85, 1])
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stock scoring, generate analysis plots, and create a JSON for the top performers.")
    parser.add_argument("--top", type=int, default=10, help="Number of top stocks to process.")
    parser.add_argument("--min-years", type=int, default=5, help="Minimum years of history required for scoring.")
    parser.add_argument("--outdir", default="plots", help="Directory to save the generated individual plot images.")
    parser.add_argument("--json-output", default="scoring_results.json", help="Path to save the output results in JSON format.")
    parser.add_argument("--plot", action="store_true", help="Generate a comparative plot of the top N stocks' normalized price performance.")
    args = parser.parse_args()

    top_stocks_data = get_ranked_stocks(min_years=args.min_years, top_n=args.top)
    if top_stocks_data:
        generate_analysis_plots(top_stocks_data, output_dir=args.outdir)

        if args.plot:
            top_stocks_for_plot = [(d['ticker'], d['score']) for d in top_stocks_data]
            plot_normalized_prices(top_stocks_for_plot, data_folder='data')

        # Save results to a JSON file
        output_json_path = args.json_output
        print(f"\n--- Saving results to {output_json_path} ---")
        # Ensure the directory for the JSON file exists
        os.makedirs(os.path.dirname(output_json_path) or '.', exist_ok=True)
        with open(output_json_path, 'w') as f:
            json.dump(top_stocks_data, f, indent=4)

        print("\n--- Report Generation Complete ---")
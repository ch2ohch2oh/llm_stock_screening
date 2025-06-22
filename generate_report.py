import os
import argparse
import json
import google.generativeai as genai
import hashlib
import fpdf
import time
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime

# --- LLM & Caching ---

def get_company_description(ticker: str, cache: dict) -> str:
    """
    Generates a company description using the Gemini API, with local caching.
    The cache key is a hash of the prompt to ensure that changes to the prompt
    invalidate the cache.

    Args:
        ticker (str): The stock ticker of the company.
        cache (dict): A dictionary used for caching results to avoid repeated API calls.

    Returns:
        str: A one-paragraph description of the company's business.
    """
    # Define the prompt first to generate the cache key
    prompt = (
        f"As a financial analyst, provide a concise, one-sentence summary for the company with the stock ticker {ticker}. "
        "Then, provide 3 concise reasons to invest and 3 reasons not to invest with solid justification. "
        "Use only <p> <b> <ul> <li> and <br> HTML tags for formatting. "
        "Use ASCII characters only, no emojis or special characters. "
        "Return the response without any markdown code fences or triple backticks."
    )
    prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()

    # 1. Check for the description in the cache first
    if prompt_hash in cache:
        print(f"  -> Found cached description for {ticker} (hash: {prompt_hash[:7]}...).")
        return cache[prompt_hash]

    # 2. If not in cache, proceed with API call
    fallback_description = (
        f"A description for {ticker} could not be generated at this time. This company operates "
        "within its respective industry, and its performance is a subject of market analysis."
    )

    api_key = os.getenv("GOOGLE_API_KEY")
    assert api_key, "GOOGLE_API_KEY environment variable must be set."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # The prompt is already defined above
        response = model.generate_content(prompt)
        description = response.text.strip()
        time.sleep(4)  # Add a 4-second delay here

        # 3. Store the new description in the cache for future use
        cache[prompt_hash] = description
        return description

    except Exception as e:
        print(f"Error calling Gemini API for {ticker}: {e}")
        return fallback_description

# --- PDF Generation ---

class PDF(FPDF):
    """Custom PDF class to include a page number footer."""

    def footer(self):
        # Don't draw a footer on the cover page (page 1)
        if self.page_no() == 1:
            return
        self.set_y(-15)  # Position 1.5 cm from bottom
        self.set_font('Helvetica', 'I', 8)
        # Adjust page number to account for the cover page
        self.cell(0, 10, f'Page {self.page_no() - 1}', align='C')

def add_cover_page(pdf: PDF, title: str, num_reports: int):
    """
    Adds a cover page to the PDF document.

    Args:
        pdf (PDF): The FPDF object.
        title (str): The main title for the cover page.
        num_reports (int): The number of stocks included in the report.
    """
    pdf.add_page()

    # Set font for the main title
    pdf.set_font('Helvetica', 'B', 40)
    # Move down to not be at the very top
    pdf.ln(60)
    # Add title, centered
    pdf.cell(0, 20, title, 0, 1, 'C')

    # Subtitle
    pdf.set_font('Helvetica', '', 20)
    pdf.cell(0, 20, "Top Stock Analysis Report", 0, 1, 'C')
    pdf.ln(10)

    # Date
    current_date = datetime.now().strftime('%B %d, %Y')
    pdf.set_font('Helvetica', 'I', 12)
    pdf.cell(0, 15, f"Generated on: {current_date}", 0, 1, 'C')
    pdf.ln(20)

    # Report summary
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, f"This document provides a detailed analysis of the top {num_reports} performing stocks.", 0, 1, 'C')

def add_report_page(pdf: PDF, stock_data: dict, cache: dict):
    """
    Adds a new page to an existing PDF object with the analysis for one stock.

    Args:
        pdf (PDF): The FPDF object to which the page will be added.
        stock_data (dict): A dictionary containing info like ticker, score, and figure path.
        cache (dict): The cache dictionary to pass to the description generator.

    Returns:
        None
    """
    ticker = stock_data.get('ticker', 'N/A').upper()
    score = stock_data.get('score')
    image_path = stock_data.get('figure')

    if not image_path or not os.path.exists(image_path):
        print(f"Warning: Figure not found for {ticker} at '{image_path}'. Skipping.")
        return

    # Get company description from LLM (with caching)
    description_html = get_company_description(ticker, cache)

    # --- Add Page and Content ---
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(w=0, h=15, text=f'Analysis Report: {ticker}', border=0, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Sub-header with score
    if score is not None:
        pdf.set_font('Helvetica', 'I', 12)
        pdf.cell(w=0, h=10, text=f'Screening Score: {score:.4f}', border=0, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(5)  # Add some space

    # Company Description
    pdf.set_font('Helvetica', '', 10)
    # Set a more spacious line height (as a multiplier of font size) before writing HTML
    pdf.line_height = 1.5
    pdf.write_html(description_html)
    pdf.line_height = 1.25  # Reset to default to avoid affecting other elements
    pdf.ln(10)  # Add 10mm of vertical space

    # Plot Image
    # A4 page width is 210mm. With 10mm margins, usable width is 190mm.
    pdf.image(image_path, w=190)

def main():
    """Main function to generate a single combined PDF report from a JSON results file."""
    parser = argparse.ArgumentParser(description="Generate a single combined PDF report from a JSON results file.")
    parser.add_argument("--input-json", default="scoring_results.json", help="Path to the JSON file containing scoring results.")
    parser.add_argument("--output-dir", default="reports", help="Directory to save the generated PDF files.")
    parser.add_argument("--cache-file", default=".gemini_cache.json", help="Path to the cache file for LLM responses.")
    parser.add_argument("--filename", default="Combined_Stock_Report.pdf", help="Base filename for the combined PDF report. A timestamp will be appended.")
    parser.add_argument("--top", type=int, help="Limit the report to the top N tickers from the JSON file.")
    args = parser.parse_args()

    if not os.path.exists(args.input_json):
        print(f"Error: Input JSON file not found at '{args.input_json}'")
        print("Please run 'python generate_scoring.py' first to create the results file.")
        return

    # --- Cache Loading ---
    llm_cache = {}
    if os.path.exists(args.cache_file):
        try:
            with open(args.cache_file, 'r') as f:
                llm_cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Warning: Could not read or parse cache file at '{args.cache_file}'. Starting with an empty cache.")
    try:
        with open(args.input_json, 'r') as f:
            report_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading or parsing JSON file: {e}")
        return

    if not report_data:
        print(f"No data found in '{args.input_json}'.")
        return

    # Limit the number of tickers to process if --top is specified
    if args.top is not None and args.top > 0:
        report_data = report_data[:args.top]
        print(f"--- Limiting report to the top {len(report_data)} tickers ---")

    # --- PDF Setup ---
    os.makedirs(args.output_dir, exist_ok=True)
    pdf = PDF('P', 'mm', 'A4')  # Create a single PDF object

    # Add the cover page before any other content
    add_cover_page(pdf, "Summit Capital Research", len(report_data))

    print(f"--- Generating Combined PDF with {len(report_data)} reports ---")
    for i, stock_data in enumerate(report_data):
        rank = stock_data.get('ranking', i + 1)
        ticker = stock_data.get('ticker', 'N/A')
        print(f"  [{rank}/{len(report_data)}] Adding report for {ticker}...")

        add_report_page(pdf, stock_data, llm_cache)

    # --- Save the final combined PDF ---
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_base, filename_ext = os.path.splitext(args.filename)
    new_filename = f"{filename_base}_{timestamp}{filename_ext}"
    output_filepath = os.path.join(args.output_dir, new_filename)
    pdf.output(output_filepath)
    print(f"\n--- Report successfully saved to: {os.path.abspath(output_filepath)} ---")

    # --- Cache Saving ---
    try:
        with open(args.cache_file, 'w') as f:
            json.dump(llm_cache, f, indent=4)
        print(f"--- LLM cache updated and saved to: {os.path.abspath(args.cache_file)} ---")
    except IOError as e:
        print(f"Error saving LLM cache: {e}")

if __name__ == "__main__":
    main()
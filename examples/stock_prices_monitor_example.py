"""
Stock Prices Monitor - Terminal Dashboard

This example demonstrates how to:
1. Fetch stock prices using the MarketData SDK
2. Display prices in a terminal table with auto-refresh
3. Highlight changed values (green for up, red for down)
4. Sort by percentage change

Requirements:
    pip install rich pandas

Note: rich and pandas are not dependencies of this SDK and must be installed separately.
"""

import threading
import time
import traceback
from datetime import datetime
from typing import List, Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat
from marketdata.sdk_error import MarketDataClientErrorResult


class StockPriceTracker:
    """Displays stock prices with color coding."""

    def __init__(self):
        self.console = Console()

    def fetch_prices(
        self, client: MarketDataClient, symbols: List[str]
    ) -> Optional[pd.DataFrame]:
        """Fetch stock prices for given symbols."""
        try:
            result = client.stocks.prices(symbols, output_format=OutputFormat.DATAFRAME)

            if isinstance(result, MarketDataClientErrorResult):
                self.console.print(f"[red]Error fetching prices: {result.error}[/red]")
                return None

            if result is None or result.empty:
                self.console.print("[yellow]No data returned from API[/yellow]")
                return None

            return result
        except (ValueError, AttributeError, KeyError) as e:
            self.console.print(f"[red]Error processing data: {str(e)}[/red]")
            return None

    def create_table(self, df: pd.DataFrame):
        """Create a rich table with highlighted changes."""

        df = df.sort_values(by="changepct", ascending=False)

        # Create table
        table = Table(
            title="📈 Stock Prices Monitor",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", justify="right", style="yellow")
        table.add_column("Change ($)", justify="right")
        table.add_column("Change (%)", justify="right")

        # Process each row
        for idx, row in df.iterrows():
            symbol = idx

            # Get price values
            price = float(row.get("mid", 0))
            change = float(row.get("change", 0))
            change_pct = float(row.get("changepct", 0))

            # Format price (no color, just the value)
            price_str = f"${price:.2f}"

            # Format percentage change with color based on positive/negative/zero
            if change_pct > 0:
                change_pct_str = f"[green]{change_pct:+.2f}%[/]"
            elif change_pct < 0:
                change_pct_str = f"[red]{change_pct:+.2f}%[/]"
            else:
                change_pct_str = f"{change_pct:+.2f}%"

            # Format dollar change with color based on positive/negative/zero
            if change > 0:
                change_str = f"[green]${change:+.2f}[/]"
            elif change < 0:
                change_str = f"[red]${change:+.2f}[/]"
            else:
                change_str = f"${change:+.2f}"

            table.add_row(symbol, price_str, change_str, change_pct_str)

        return table

    def display(
        self,
        df: pd.DataFrame,
        symbols: List[str],
        refresh_interval: int,
        clear_screen: bool = True,
    ):
        """Display the table."""
        table = self.create_table(df)
        if clear_screen:
            self.console.clear()
        self.console.print(table)

        # Show controls and input prompt
        controls = Panel(
            f"[dim]Commands: -a SYMBOL (add), -r SYMBOL (remove), -l (list), q (quit) | Refresh: {refresh_interval}s[/dim]\n"
            f"[dim]Monitoring: {', '.join(symbols)}[/dim]\n"
            f"[dim]Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            title="Controls",
            border_style="dim",
        )
        self.console.print(controls)
        self.console.print("\n[dim]Command:[/dim]", end=" ")


# Shared state between threads


class MonitorState:
    def __init__(self):
        self.symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
        self.running = True
        self.lock = threading.Lock()
        self.refresh_interval = 10
        self.user_inputting = False  # Flag to pause display updates during input


def main():
    """Main function to run the stock prices monitor."""

    state = MonitorState()

    # Initialize
    tracker = StockPriceTracker()
    console = Console()

    # Initialize client
    try:
        client = MarketDataClient()  # add token here
        client.default_params.output_format = OutputFormat.DATAFRAME
    except ValueError as e:
        console.print(f"[red]Client initialization error: {str(e)}[/red]")
        console.print(
            "[yellow]Please set your MarketData token in environment variables or pass it to MarketDataClient()[/yellow]"
        )
        return

    def display_loop():
        """Continuously update the display."""
        console.print("[green]Starting stock prices monitor...[/green]")
        with state.lock:
            console.print(f"[dim]Monitoring: {', '.join(state.symbols)}[/dim]")
        console.print(f"[dim]Refresh interval: {state.refresh_interval} seconds[/dim]")
        console.print(
            "[dim]Type commands: -a SYMBOL (add), -r SYMBOL (remove), -l (list), q (quit)[/dim]\n"
        )

        # Do first update immediately
        first_update = True

        while state.running:
            try:
                # Get current symbols (thread-safe)
                with state.lock:
                    current_symbols = state.symbols.copy()

                # Fetch prices
                df = tracker.fetch_prices(client, current_symbols)

                if df is not None and not df.empty:
                    # Always display table with live updates
                    # Only clear screen on first update or if not first update
                    tracker.display(
                        df, current_symbols, state.refresh_interval, clear_screen=True
                    )
                    first_update = False
                else:
                    # Show error state
                    if not first_update:
                        console.clear()
                    console.print("[red]Error fetching data. Retrying...[/red]")
                    first_update = False

                # Wait for next refresh (check more frequently)
                elapsed = 0
                while elapsed < state.refresh_interval and state.running:
                    time.sleep(0.5)
                    elapsed += 0.5
            except Exception as e:
                console.print(f"[red]Error in display loop: {e}[/red]")
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
                time.sleep(1)

    def input_loop():
        """Handle user input in a separate thread."""
        time.sleep(3)  # Give display time to start

        while state.running:
            try:
                # Wait for input (prompt is shown by display thread)
                user_input = input().strip()

                if not user_input:
                    continue

                if user_input.lower() == "q":
                    with state.lock:
                        state.running = False
                    break
                elif user_input.lower() == "-l" or user_input.lower() == "l":
                    # List current symbols
                    with state.lock:
                        current = state.symbols.copy()
                    console.print(f"[cyan]Current symbols: {', '.join(current)}[/cyan]")
                elif user_input.startswith("-a ") or user_input.startswith("a "):
                    # Add symbols: -a AAPL or -a AAPL,GOOGL
                    symbols_to_add = (
                        user_input[3:].strip()
                        if user_input.startswith("-a ")
                        else user_input[2:].strip()
                    )
                    if symbols_to_add:
                        new_symbols = [
                            s.strip().upper()
                            for s in symbols_to_add.split(",")
                            if s.strip()
                        ]
                        if new_symbols:
                            with state.lock:
                                added = []
                                for sym in new_symbols:
                                    if sym not in state.symbols:
                                        state.symbols.append(sym)
                                        added.append(sym)
                                if added:
                                    console.print(
                                        f"[green]Added: {', '.join(added)}[/green]"
                                    )
                                    console.print(
                                        f"[dim]Current symbols: {', '.join(state.symbols)}[/dim]"
                                    )
                                else:
                                    console.print(
                                        f"[yellow]Symbols already in list: {', '.join(new_symbols)}[/yellow]"
                                    )
                        else:
                            console.print("[yellow]No valid symbols to add[/yellow]")
                    else:
                        console.print(
                            "[yellow]Usage: -a SYMBOL or -a SYMBOL1,SYMBOL2[/yellow]"
                        )
                elif user_input.startswith("-r ") or user_input.startswith("r "):
                    # Remove symbols: -r TSLA or -r TSLA,MSFT
                    symbols_to_remove = (
                        user_input[3:].strip()
                        if user_input.startswith("-r ")
                        else user_input[2:].strip()
                    )
                    if symbols_to_remove:
                        symbols_to_remove_list = [
                            s.strip().upper()
                            for s in symbols_to_remove.split(",")
                            if s.strip()
                        ]
                        if symbols_to_remove_list:
                            with state.lock:
                                removed = []
                                for sym in symbols_to_remove_list:
                                    if sym in state.symbols:
                                        state.symbols.remove(sym)
                                        removed.append(sym)
                            if removed:
                                console.print(
                                    f"[green]Removed: {', '.join(removed)}[/green]"
                                )
                                if state.symbols:
                                    console.print(
                                        f"[dim]Current symbols: {', '.join(state.symbols)}[/dim]"
                                    )
                                else:
                                    console.print(
                                        "[yellow]No symbols remaining. Add some with -a SYMBOL[/yellow]"
                                    )
                            else:
                                console.print(
                                    f"[yellow]Symbols not in list: {', '.join(symbols_to_remove_list)}[/yellow]"
                                )
                        else:
                            console.print("[yellow]No valid symbols to remove[/yellow]")
                    else:
                        console.print(
                            "[yellow]Usage: -r SYMBOL or -r SYMBOL1,SYMBOL2[/yellow]"
                        )
                else:
                    console.print(f"[yellow]Unknown command: {user_input}[/yellow]")
                    console.print(
                        "[dim]Use -a SYMBOL to add, -r SYMBOL to remove, -l to list, q to quit[/dim]"
                    )

            except (EOFError, KeyboardInterrupt):
                with state.lock:
                    state.running = False
                break
            except Exception as e:
                console.print(f"[red]Error in input loop: {e}[/red]")
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
                time.sleep(0.5)

    # Start display thread
    display_thread = threading.Thread(target=display_loop, daemon=True)
    display_thread.start()

    # Start input thread
    input_thread = threading.Thread(target=input_loop, daemon=True)
    input_thread.start()

    try:
        # Keep main thread alive
        while state.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        with state.lock:
            state.running = False

    # Wait for threads to finish
    display_thread.join(timeout=1)
    input_thread.join(timeout=1)

    console.print("\n[yellow]Stopping monitor...[/yellow]")


if __name__ == "__main__":
    main()

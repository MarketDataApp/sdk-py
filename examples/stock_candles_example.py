"""
Example: Create a candlestick chart with volume and Bollinger bands using finplot

This example demonstrates how to:
1. Fetch stock candles data using the MarketData  as a pandas DataFrame
2. Plot the candles using finplot library with volume and Bollinger bands

Requirements:
    pip install finplot pandas

Note: finplot and pandas are not dependencies of this SDK and must be installed separately.
"""

from datetime import datetime, timedelta

import finplot as fplt

from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

VOL_SCALE = 1e6


def main():
    # Initialize the client
    client = MarketDataClient()  # Add your token here
    client.default_params.output_format = OutputFormat.DATAFRAME

    # Fetch stock candles for AAPL with daily resolution for the last year.
    symbol = "AAPL"
    resolution = "D"
    days_to_fetch = 365

    from_date = (datetime.now() - timedelta(days=days_to_fetch)).date()
    to_date = datetime.now().date()

    df = client.stocks.candles(
        symbol, resolution=resolution, from_date=from_date, to_date=to_date
    )

    # Create a finplot chart with two subplots:
    # - Top plot: Candlestick chart showing OHLC data
    # - Bottom plot: Volume bars
    ax, axv = fplt.create_plot(f"{symbol} - {resolution}", rows=2)
    ax.set_visible(xgrid=True, ygrid=True)

    # Plot candles
    df[["o", "c", "h", "l"]].plot(ax=ax, kind="candle")

    # Add volume to chart
    # Divide volume data by 1e6 for display in millions
    df["v"] = df["v"] / VOL_SCALE
    df[["o", "c", "v"]].plot(ax=axv, kind="volume")
    axv.axes["right"]["item"].setLabel("Volume (M)")

    # Add Bollinger Bands
    # Calculate {periods} moving average and standard deviation
    periods = 20
    std_deviations = 2

    mean = df.c.rolling(periods).mean()
    mean.plot(ax=ax, color="#c0c030")
    stddev = df.c.rolling(periods).std()

    # Plot upper and lower bands (mean +- {std_deviations} * stddev)
    df["boll_hi"] = mean + std_deviations * stddev
    df["boll_lo"] = mean - std_deviations * stddev
    p0 = df.boll_hi.plot(ax=ax, color="green", legend="BB")
    p1 = df.boll_lo.plot(ax=ax, color="red")
    fplt.fill_between(p0, p1, color="#bbb")
    fplt.autoviewrestore()

    # Display the plot
    fplt.show()


if __name__ == "__main__":
    main()

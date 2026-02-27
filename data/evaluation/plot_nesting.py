import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse

def plot_computation_nesting(csv_path):
    # Read the CSV file
    print(f"Reading CSV file: {csv_path}")

    # Read CSV with tab delimiter, assuming columns: astNodeId, eventName, astNodeName, timestamp
    df = pd.read_csv(csv_path, sep='\t', header=None, names=['astNodeId', 'eventName', 'astNodeName', 'timestamp'])
    print(f"Loaded {len(df):,} total events from CSV")

    # Count COMPUTE_BEGIN and COMPUTE_END events
    compute_event_count = df['eventName'].isin(['COMPUTE_BEGIN', 'COMPUTE_END']).sum()
    print(f"Found {compute_event_count:,} computation events (COMPUTE_BEGIN/COMPUTE_END)")
    print(f"Processing all {len(df):,} events (keeping nesting level constant for non-compute events)")

    if df.empty:
        print("No events found in the log file.")
        return

    # Track nesting level over time using vectorized operations
    print("Calculating nesting levels (vectorized)...")

    # Convert to numpy arrays for faster processing
    timestamps_raw = df['timestamp'].values
    event_types = df['eventName'].values

    # Convert event types to deltas: +1 for BEGIN, -1 for END, 0 for everything else
    deltas = np.where(event_types == 'COMPUTE_BEGIN', 1,
                     np.where(event_types == 'COMPUTE_END', -1, 0))

    # Calculate cumulative nesting levels
    cumulative_levels = np.cumsum(deltas)

    # Level before each event: shift cumulative by 1, starting at 0
    levels_before = np.concatenate([[0], cumulative_levels[:-1]])
    levels_after = cumulative_levels

    # Interleave timestamps and levels to create step plot
    # For each event: (timestamp, level_before), (timestamp, level_after)
    timestamps = np.repeat(timestamps_raw, 2)
    nesting_levels = np.empty(len(timestamps_raw) * 2, dtype=int)
    nesting_levels[0::2] = levels_before  # Even indices: before
    nesting_levels[1::2] = levels_after   # Odd indices: after

    # Duplicate event types to match the interleaved timestamps
    event_types_plot = np.repeat(event_types, 2)

    print(f"Finished processing all {len(df):,} events")

    # # Normalize timestamps to start from 0
    # print("Normalizing timestamps...")
    # min_t = min(timestamps)
    # timestamps = [t - min_t for t in timestamps]

    # Create the plot
    print("Creating scatter plot...")
    plt.figure(figsize=(14, 6))

    # Downsample for faster rendering (plot every Nth point)
    downsample_factor = max(1, len(timestamps) // 1000000)  # Target ~100k points
    # downsample_factor = 1
    print(f"Downsampling by factor of {downsample_factor} for visualization")

    timestamps_plot = timestamps[::downsample_factor]
    nesting_levels_plot = nesting_levels[::downsample_factor]
    event_types_sampled = event_types_plot[::downsample_factor]

    # Plot COMPUTE_BEGIN and COMPUTE_END in distinct colors, others in gray
    mask_begin = event_types_sampled == 'COMPUTE_BEGIN'
    mask_end = event_types_sampled == 'COMPUTE_END'
    mask_other = ~(mask_begin | mask_end)

    # Plot others first (in background)
    if mask_other.any():
        plt.scatter(timestamps_plot[mask_other], nesting_levels_plot[mask_other],
                   c='lightgray', alpha=0.3, s=1, label='Other events')

    # Plot BEGIN and END events on top
    if mask_begin.any():
        plt.scatter(timestamps_plot[mask_begin], nesting_levels_plot[mask_begin],
                   c='green', alpha=0.7, s=2, label='COMPUTE_BEGIN')
    if mask_end.any():
        plt.scatter(timestamps_plot[mask_end], nesting_levels_plot[mask_end],
                   c='red', alpha=0.7, s=2, label='COMPUTE_END')

    plt.xlabel("Time (nanoseconds from start)", fontsize=12)
    plt.ylabel("Nesting Level", fontsize=12)
    plt.title("Computation Event Nesting Levels Over Time (Downsampled)", fontsize=14, fontweight='bold')
    plt.legend(loc='upper right', fontsize=9)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    # Display stats
    max_level = nesting_levels.max() if len(nesting_levels) > 0 else 0
    print("\n" + "="*60)
    print("STATISTICS:")
    print("="*60)
    print(f"Maximum nesting level: {max_level}")
    print(f"Total events processed: {len(df):,}")
    print(f"Computation events (BEGIN/END): {compute_event_count:,}")
    print(f"Time range: {timestamps[-1]:,} ns ({timestamps[-1] / 1e9:.3f} seconds)")
    print("="*60 + "\n")

    # Save plot to file
    output_path = Path(__file__).parent / "nesting_levels_plot.png"
    print(f"Saving plot to: {output_path}")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Plot saved successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Plot computation event nesting levels over time')
    parser.add_argument('csv_file', nargs='?', default=None,
                        help='Path to the CSV log file (default: log.csv in script directory)')
    args = parser.parse_args()

    # Use provided path or default to log.csv in the script's directory
    if args.csv_file:
        csv_path = Path(args.csv_file)
    else:
        csv_path = Path(__file__).parent / "log.csv"

    plot_computation_nesting(csv_path)

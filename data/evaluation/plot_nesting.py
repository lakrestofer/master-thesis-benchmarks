import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import hashlib

def string_to_hex_color(text: str) -> str:
    """
    Converts a string into a deterministic hex color code.
    Example: "hello" -> "#5d4140"
    """
    if type(text) is not str:
        return "#000000"
    # Create SHA-256 hash of the string
    hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()

    # Use first 3 bytes for RGB
    r, g, b = hash_bytes[0], hash_bytes[1], hash_bytes[2]

    return f'#{r:02x}{g:02x}{b:02x}'

def plot_computation_nesting(csv_path):
    # Read the CSV file
    print(f"Reading CSV file: {csv_path}")

    # Read CSV with tab delimiter, assuming columns: timestamp, astNodeId, astNodeName, attribute, eventName
    # Explicitly set aspect as string type to avoid sorting/type issues
    df = pd.read_csv(csv_path, sep='\t', header=None,
                     names=['timestamp', 'aspect', 'astNodeId', 'astNodeName', 'attribute', 'eventName'],
                     dtype={'aspect': str, 'astNodeName': str, 'attribute': str, 'eventName': str})
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
    aspects = df['aspect'].values

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

    # Duplicate event types and aspects to match the interleaved timestamps
    event_types_plot = np.repeat(event_types, 2)
    aspects_plot = np.repeat(aspects, 2)

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
    aspects_sampled = aspects_plot[::downsample_factor]

    # Get unique aspects and create color mapping
    unique_aspects = df['aspect'].unique()
    aspect_colors = {aspect: string_to_hex_color(aspect) for aspect in unique_aspects}
    print(f"Found {len(unique_aspects)} unique aspects")

    # Plot the line connecting all points
    plt.plot(timestamps_plot, nesting_levels_plot, color='lightgray', alpha=0.2, linewidth=0.5, zorder=1)

    # Plot each aspect with its unique color
    for aspect in unique_aspects:
        mask = aspects_sampled == aspect
        if mask.any():
            plt.scatter(timestamps_plot[mask], nesting_levels_plot[mask],
                       c=aspect_colors[aspect], alpha=0.7, s=2, label=aspect, zorder=2)

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
    print(f"Unique aspects: {len(unique_aspects)}")
    print(f"Time range: {timestamps[-1]:,} ns ({timestamps[-1] / 1e9:.3f} seconds)")
    print("="*60 + "\n")

    # Save plot to file
    output_path = Path(__file__).parent / "nesting_levels_plot.png"
    print(f"Saving plot to: {output_path}")
    # plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
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

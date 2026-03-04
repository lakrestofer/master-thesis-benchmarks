from sys import exit
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import hashlib
from scipy.spatial import KDTree
import time
from enum import Enum

############################################################
# Type definitions
############################################################

class RenderingMode(Enum):
    File = "file"
    Gui = "gui"

    def __str__(self):
        return self.value

############################################################
# Util functions
#############################################################

def string_to_hex_color(text: str) -> str:
    """
    Converts a string into a deterministic hex color code.
    Example: "hello" -> "#5d4140"
    """
    if type(text) is not str:
        return "#000000"
    # Create SHA-256 hash of the string
    # TODO we probably do not need a crypographically secure hash here :D
    hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()

    # Use first 3 bytes for RGB
    r, g, b = hash_bytes[0], hash_bytes[1], hash_bytes[2]

    return f'#{r:02x}{g:02x}{b:02x}'

def plot_computation_nesting(csv_path):
    # Track timing for all major steps
    timings = {}
    overall_start = time.perf_counter()

    # Read the CSV file
    print(f"Reading CSV file: {csv_path}")

    # Time the CSV parsing
    step_start = time.perf_counter()

    # Read CSV with tab delimiter, assuming columns: timestamp, astNodeId, astNodeName, attribute, eventName
    # Explicitly set aspect as string type to avoid sorting/type issues
    df = pd.read_csv(csv_path, sep='\t', header=None,
                     names=['timestamp', 'aspect', 'astNodeId', 'astNodeName', 'attribute', 'eventName'],
                     dtype={'aspect': str, 'astNodeName': str, 'attribute': str, 'eventName': str})

    timings['csv_parsing'] = time.perf_counter() - step_start

    print(f"Loaded {len(df):,} total events from CSV (took {timings['csv_parsing']:.3f}s)")

    # Count COMPUTE_BEGIN and COMPUTE_END events
    compute_event_count = df['eventName'].isin(['COMPUTE_BEGIN', 'COMPUTE_END']).sum()
    print(f"Found {compute_event_count:,} computation events (COMPUTE_BEGIN/COMPUTE_END)")
    print(f"Processing all {len(df):,} events (keeping nesting level constant for non-compute events)")

    if df.empty:
        print("No events found in the log file.")
        return

    # Track nesting level over time using vectorized operations
    print("Calculating nesting levels (vectorized)...")
    step_start = time.perf_counter()

    # Convert to numpy arrays for faster processing
    timestamps_raw = df['timestamp'].values
    event_types = df['eventName'].values
    attributes = df['attribute'].values
    aspects = df['aspect'].values

    # Convert event types to deltas: +1 for BEGIN, -1 for END, 0 for everything else
    deltas = np.where(event_types == 'COMPUTE_BEGIN', 1,
                     np.where(event_types == 'COMPUTE_END', -1, 0))

    # Calculate cumulative nesting levels (level after each event)
    nesting_levels = np.cumsum(deltas)

    # Use raw data directly - one point per event (no duplication)
    timestamps = timestamps_raw

    timings['nesting_calculation'] = time.perf_counter() - step_start
    print(f"Finished processing all {len(df):,} events (took {timings['nesting_calculation']:.3f}s)")

    # # Normalize timestamps to start from 0
    # print("Normalizing timestamps...")
    # min_t = min(timestamps)
    # timestamps = [t - min_t for t in timestamps]

    # Get unique aspects and create color mapping
    step_start = time.perf_counter()
    unique_aspects = df['aspect'].unique()
    aspect_colors = {aspect: string_to_hex_color(aspect) for aspect in unique_aspects}
    timings['aspect_colors'] = time.perf_counter() - step_start
    print(f"Found {len(unique_aspects)} unique aspects (took {timings['aspect_colors']:.3f}s)")

    # Create the plot with dynamic height based on number of aspects
    print("Creating scatter plot...")
    step_start = time.perf_counter()
    # Calculate figure height to accommodate legend (minimum 8, scale with aspects, max 20)
    fig_height = max(8, min(20, 8 + len(unique_aspects) * 0.15))
    fig, ax = plt.subplots(figsize=(18, fig_height))

    # Downsample for faster rendering (plot every Nth point)
    # downsample_factor = max(1, len(timestamps) // 1000000)  # Target ~100k points
    downsample_factor = 1
    print(f"Downsampling by factor of {downsample_factor} for visualization")

    timestamps_plot = timestamps[::downsample_factor]
    nesting_levels_plot = nesting_levels[::downsample_factor]
    event_types_sampled = event_types[::downsample_factor]
    aspects_sampled = aspects[::downsample_factor]
    attributes_sampled = attributes[::downsample_factor]
    timings['plot_setup'] = time.perf_counter() - step_start

    # Plot the line connecting all points
    step_start = time.perf_counter()
    # ax.plot(timestamps_plot, nesting_levels_plot, color='lightgray', alpha=0.5, linewidth=0.5, zorder=1)
    ax.plot(timestamps_plot, nesting_levels_plot, color='lightgray', linewidth=0.25, zorder=1)

    # Plot each aspect with its unique color
    for aspect in unique_aspects:
        mask = aspects_sampled == aspect
        if mask.any():
            ax.scatter(timestamps_plot[mask], nesting_levels_plot[mask],
                       c=aspect_colors[aspect], alpha=0.7, s=2, label=aspect, zorder=2)
    timings['plotting'] = time.perf_counter() - step_start
    print(f"Plotting complete (took {timings['plotting']:.3f}s)")

    # Build KD-tree for fast hover lookup
    step_start = time.perf_counter()
    # Normalize coordinates for KD-tree (timestamps and levels have very different scales)
    timestamp_range = timestamps_plot.max() - timestamps_plot.min()
    level_range = nesting_levels_plot.max() - nesting_levels_plot.min()
    level_range = max(level_range, 1)  # Avoid division by zero

    points_normalized = np.column_stack([
        (timestamps_plot - timestamps_plot.min()) / timestamp_range,
        (nesting_levels_plot - nesting_levels_plot.min()) / level_range
    ])
    kdtree = KDTree(points_normalized)
    timings['kdtree_build'] = time.perf_counter() - step_start

    print(f"Built KD-tree with {len(points_normalized):,} points for fast hover lookup (took {timings['kdtree_build']:.3f}s)")

    step_start = time.perf_counter()
    ax.set_xlabel("Time (nanoseconds from start)", fontsize=12)
    ax.set_ylabel("Nesting Level", fontsize=12)
    ax.set_title("Computation Event Nesting Levels Over Time (Downsampled)", fontsize=14, fontweight='bold')

    # Place legend outside plot area with multiple columns and smaller font
    # Calculate number of columns based on number of aspects (max 3 columns)
    # ncols = min(3, max(1, len(unique_aspects) // 10))
    # ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=7,
    #           ncol=ncols, framealpha=0.9, markerscale=2)

    ax.grid(True, alpha=0.3)

    # Add hover tooltip functionality using KD-tree for fast lookup
    annot = ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                        bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.9),
                        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
                        fontsize=9, visible=False, zorder=10)

    def hover(event):
        if event.inaxes == ax and event.xdata is not None and event.ydata is not None:
            # Normalize mouse position to match KD-tree coordinates
            mouse_x_norm = (event.xdata - timestamps_plot.min()) / timestamp_range
            mouse_y_norm = (event.ydata - nesting_levels_plot.min()) / level_range

            # Find nearest point using KD-tree (very fast!)
            distance, idx = kdtree.query([mouse_x_norm, mouse_y_norm])

            # Only show tooltip if mouse is close enough (threshold in normalized space)
            # Adjust threshold based on plot size - smaller threshold = need to be closer
            threshold = 0.01  # Normalized distance threshold
            if distance < threshold:
                x_val = timestamps_plot[idx]
                y_val = nesting_levels_plot[idx]
                aspect = aspects_sampled[idx]
                event = event_types_sampled[idx]
                attribute = attributes_sampled[idx]

                annot.xy = (x_val, y_val)
                annot.set_text(f"Aspect: {aspect}\nAttribute: {attribute}\nEvent: {event}")
                annot.set_visible(True)
                fig.canvas.draw_idle()
            elif annot.get_visible():
                annot.set_visible(False)
                fig.canvas.draw_idle()
        elif annot.get_visible():
            annot.set_visible(False)
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", hover)
    timings['plot_finalization'] = time.perf_counter() - step_start

    plt.tight_layout()

    timings['total'] = time.perf_counter() - overall_start

    # Display detailed timing breakdown
    print("\n" + "="*60)
    print("PERFORMANCE TIMING BREAKDOWN:")
    print("="*60)
    file_size_mb = csv_path.stat().st_size / (1024*1024)
    print(f"CSV Parsing:          {timings['csv_parsing']:>8.3f}s  ({file_size_mb/timings['csv_parsing']:>6.1f} MB/s)")
    print(f"Nesting Calculation:  {timings['nesting_calculation']:>8.3f}s  ({len(df)/timings['nesting_calculation']:>6.0f} events/s)")
    print(f"Aspect Colors:        {timings['aspect_colors']:>8.3f}s")
    print(f"Plot Setup:           {timings['plot_setup']:>8.3f}s")
    print(f"Plotting:             {timings['plotting']:>8.3f}s")
    print(f"KD-tree Build:        {timings['kdtree_build']:>8.3f}s")
    print(f"Plot Finalization:    {timings['plot_finalization']:>8.3f}s")
    print("-" * 60)
    print(f"TOTAL TIME:           {timings['total']:>8.3f}s")
    print("="*60)

    # Calculate percentages
    print("\nTime Distribution:")
    for step, duration in sorted(timings.items(), key=lambda x: x[1], reverse=True):
        if step != 'total':
            percentage = (duration / timings['total']) * 100
            print(f"  {step:.<25} {percentage:>5.1f}%")
    print("="*60 + "\n")

    # Display stats
    max_level = nesting_levels.max() if len(nesting_levels) > 0 else 0
    print("DATA STATISTICS:")
    print("="*60)
    print(f"Maximum nesting level: {max_level}")
    print(f"Total events processed: {len(df):,}")
    print(f"Computation events (BEGIN/END): {compute_event_count:,}")
    print(f"Unique aspects: {len(unique_aspects)}")
    print(f"Time range: {timestamps[-1]:,} ns ({timestamps[-1] / 1e9:.3f} seconds)")
    print(f"File size: {file_size_mb:.2f} MB")
    print("="*60 + "\n")

    # Save plot to file
    plt.show()
    plt.tight_layout()

    output_path = Path(__file__).parent / "nesting_levels_plot.png"
    print(f"Saving plot to: {output_path}")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    # print("Plot saved successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Plot computation event nesting levels over time')
    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to the CSV log file (default: log.csv in script directory)',
    )
    parser.add_argument(
        '--render_output',
        default=RenderingMode.Gui,
        type=RenderingMode,
        choices=list(RenderingMode),
        help='How this script should render the graphs, to a file, or to an interactive gui',
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    rendering_mode = args.render_output

    print(f"reading file {csv_path}")
    print(f"rendering mode {rendering_mode}")

    plot_computation_nesting(csv_path)

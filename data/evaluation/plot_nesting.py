from pandas import DataFrame
from sys import exit
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import CheckButtons
from matplotlib.widgets import Button
from pathlib import Path
import argparse
from scipy.spatial import KDTree
import time
from enum import Enum
import colorsys
from tqdm import tqdm

############################################################
# Type definitions
############################################################

class RenderingMode(Enum):
    File = "file"
    Gui = "gui"

    def __str__(self):
        return self.value

DfTimestamp = "timestamp"
DfEventName = "eventName"
DfAttribute = "attribute"
DfAspect = "aspect"

############################################################
# Util functions
############################################################

def generate_distinct_colors(n: int) -> list[str]:
    """
    Generate n visually distinct colors using golden ratio spacing in HSV space.
    This ensures maximum perceptual difference between colors.
    """
    colors = []
    golden_ratio = 0.618033988749895  # Golden ratio conjugate

    # Start with a random offset to avoid always starting with the same color
    hue = 0.0

    for i in range(n):
        # Use golden ratio to space hues maximally apart
        hue = (hue + golden_ratio) % 1.0

        # High saturation and value for vibrant, distinguishable colors
        saturation = 0.8
        value = 0.9

        # Convert HSV to RGB
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

        # Convert to hex
        hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
        colors.append(hex_color)

    return colors


############################################################
# Main compute functions
############################################################
TIMINGS = {}

def read_csv_to_dataframe(csv_path: Path, start, end):
    # Read the CSV file
    print(f"Reading CSV file: {csv_path}")
    # Time the CSV parsing
    step_start = time.perf_counter()

    # Read CSV with tab delimiter, assuming columns: timestamp, astNodeId, astNodeName, attribute, eventName
    # Explicitly set aspect as string type to avoid sorting/type issues
    df = pd.read_csv(csv_path, sep='\t', header=None, skiprows=start, nrows=end-start if end >= start else None,
                     names=['timestamp', 'aspect', 'astNodeId', 'astNodeName', 'attribute', 'eventName'],
                     dtype={'aspect': str, 'astNodeName': str, 'attribute': str, 'eventName': str})

    TIMINGS['csv_parsing'] = time.perf_counter() - step_start
    print(f"Loaded {len(df):,} total events from CSV (took {TIMINGS['csv_parsing']:.3f}s)")

    return df


def process_nesting_data(df):
    """
    Process trace data to calculate nesting levels and prepare visualization data.

    Returns:
        tuple: (df, timestamps, nesting_levels, event_types, attributes, aspects,
                aspect_colors, compute_event_count, unique_event_types)
    """
    # Count COMPUTE_BEGIN and COMPUTE_END events
    compute_event_count = df[DfTimestamp].isin(['COMPUTE_BEGIN', 'COMPUTE_END']).sum()
    print(f"Found {compute_event_count:,} computation events (COMPUTE_BEGIN/COMPUTE_END)")
    print(f"Processing all {len(df):,} events (keeping nesting level constant for non-compute events)")

    # Track nesting level over time using vectorized operations
    print("Calculating nesting levels (vectorized)...")
    step_start = time.perf_counter()

    # Convert to numpy arrays for faster processing
    timestamps = df['timestamp'].values
    event_types = df['eventName'].values
    attributes = df['attribute'].values
    aspects = df['aspect'].values

    # Convert event types to deltas: +1 for BEGIN, -1 for END, 0 for everything else
    deltas = np.where(event_types == 'COMPUTE_BEGIN', 1,
                     np.where(event_types == 'COMPUTE_END', -1, 0))

    # Calculate cumulative nesting levels (level after each event)
    nesting_levels = np.cumsum(deltas)

    TIMINGS['nesting_calculation'] = time.perf_counter() - step_start
    print(f"Finished processing all {len(df):,} events (took {TIMINGS['nesting_calculation']:.3f}s)")

    # Get unique aspects and create color mapping
    step_start = time.perf_counter()
    unique_aspects = df['aspect'].unique()

    # Generate evenly-spaced distinct colors for all aspects at once
    distinct_colors = generate_distinct_colors(len(unique_aspects))
    aspect_colors = {aspect: color for aspect, color in zip(unique_aspects, distinct_colors)}

    TIMINGS['aspect_colors'] = time.perf_counter() - step_start
    print(f"Found {len(unique_aspects)} unique aspects (took {TIMINGS['aspect_colors']:.3f}s)")

    # Collect unique event types (excluding COMPUTE_BEGIN/COMPUTE_END)
    unique_event_types = df['eventName'].unique()
    print(f"Found {len(unique_event_types)} unique event types")

    return (df, timestamps, nesting_levels, event_types, attributes, aspects,
            aspect_colors, compute_event_count, unique_event_types)


def create_nesting_level_plot(timestamps, nesting_levels, event_types, aspects, attributes, aspect_colors, unique_event_types, downsample_to: int = 10000, csv_start: int = 0):
    """
    Create an interactive nesting level plot from processed data.

    Args:
        timestamps: numpy array of timestamps
        nesting_levels: numpy array of nesting levels
        event_types: numpy array of event type names
        aspects: numpy array of aspect names
        attributes: numpy array of attribute names
        aspect_colors: dict mapping aspect names to color hex codes
        unique_event_types: list of unique event type names (excluding COMPUTE_*)

    Returns:
        matplotlib.figure.Figure: The created figure
    """
    unique_aspects = list(aspect_colors.keys())

    # Create the plot with dynamic height based on number of aspects
    print("Creating scatter plot...")
    step_start = time.perf_counter()
    # Calculate figure height to accommodate legend (minimum 8, scale with aspects, max 20)
    fig_height = max(8, min(20, 8 + len(unique_aspects) * 0.15))

    # Create figure with space for checkboxes on the right
    fig = plt.figure(figsize=(20, fig_height))

    # Use GridSpec for layout: main plot on left, controls on right
    gs = fig.add_gridspec(1, 2, width_ratios=[4, 1], wspace=0.3)
    ax = fig.add_subplot(gs[0])
    ax_checks = fig.add_subplot(gs[1])
    ax_checks.set_title("Event Type Filters", fontsize=10, fontweight='bold')
    # Hide ticks and spines but keep axes interactive
    ax_checks.set_xticks([])
    ax_checks.set_yticks([])
    for spine in ax_checks.spines.values():
        spine.set_visible(False)

    # Downsample for faster rendering (plot every Nth point)
    downsample_factor = 1
    if (downsample_to > 0):
        downsample_factor = max(1, len(timestamps) // downsample_to)  # Target ~100k points

    print(f"Downsampling by factor of {downsample_factor} for visualization")

    timestamps_plot = timestamps[::downsample_factor]
    nesting_levels_plot = nesting_levels[::downsample_factor]
    event_types_sampled = event_types[::downsample_factor]
    aspects_sampled = aspects[::downsample_factor]
    attributes_sampled = attributes[::downsample_factor]
    TIMINGS['plot_setup'] = time.perf_counter() - step_start

    # Plot the line connecting all points
    step_start = time.perf_counter()
    ax.plot(timestamps, nesting_levels, color='lightgray', linewidth=0.25, zorder=1)

    # Store scatter collections by event type for toggling
    scatter_collections = {}

    # Create mask for compute events (still exclude these)
    # mask_compute = np.isin(event_types_sampled, ['COMPUTE_BEGIN', 'COMPUTE_END'])

    # Plot each event type, organized by aspect
    for event_type in tqdm(unique_event_types):
        event_mask = event_types_sampled == event_type
        combined_mask = event_mask

        if combined_mask.any():
            # For this event type, plot each aspect with its color
            for aspect in unique_aspects:
                aspect_mask = aspects_sampled == aspect
                final_mask = combined_mask & aspect_mask

                if final_mask.any():
                    scatter = ax.scatter(
                        timestamps_plot[final_mask],
                        nesting_levels_plot[final_mask],
                        c=aspect_colors[aspect],
                        s=2,
                        label=f"{aspect}:{event_type}",
                        zorder=2
                    )
                    # Store in dict for toggling
                    if event_type not in scatter_collections:
                        scatter_collections[event_type] = []
                    scatter_collections[event_type].append(scatter)

    TIMINGS['plotting'] = time.perf_counter() - step_start
    print(f"Plotting complete (took {TIMINGS['plotting']:.3f}s)")

    # Create CheckButtons widget for event type filtering
    check_labels = list(unique_event_types)
    check_initial_state = [True] * len(check_labels)

    # Use the ax_checks subplot we already created for the checkboxes
    check = CheckButtons(ax_checks, check_labels, check_initial_state)

    # Create a separate axes for the toggle all button (positioned above checkboxes)
    button_ax = plt.axes((0.75, 0.05, 0.15, 0.05))
    toggle_button = Button(button_ax, "Toggle All")

    def toggle_all(event):
        print("Toggle All button clicked")
        # Get current states of all checkboxes
        current_states = check.get_status()

        # If all are True, set all to False; otherwise set all to True
        all_enabled = all(current_states)
        new_state = not all_enabled

        # Toggle each checkbox programmatically
        for i, label in enumerate(check_labels):
            if current_states[i] != new_state:
                check.set_active(i)  # This will trigger the toggle_event_type callback

        print(f"Set all checkboxes to: {new_state}")

    toggle_button.on_clicked(toggle_all)

    # Callback to toggle event type visibility
    def toggle_event_type(label):
        print(f"check clicked: {label}")
        # Find which event type was toggled
        if label in scatter_collections:
            for scatter in scatter_collections[label]:
                scatter.set_visible(not scatter.get_visible())
        fig.canvas.draw_idle()

    check.on_clicked(toggle_event_type)

    # Store the widgets as figure attributes to prevent garbage collection
    fig._check_buttons = check  # type: ignore
    fig._toggle_button = toggle_button  # type: ignore

    print(f"Created checkboxes for {len(unique_event_types)} event types")

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
    TIMINGS['kdtree_build'] = time.perf_counter() - step_start

    print(f"Built KD-tree with {len(points_normalized):,} points for fast hover lookup (took {TIMINGS['kdtree_build']:.3f}s)")

    step_start = time.perf_counter()
    ax.set_xlabel("Time (nanoseconds from start)", fontsize=12)
    ax.set_ylabel("Nesting Level", fontsize=12)
    ax.set_title("Computation Event Nesting Levels Over Time" + (" (Downsampled)" if downsample_to > 0 else ""), fontsize=14, fontweight='bold')

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

            # if event_types_sampled[idx].startswith('COMPUTE_'):
            #     return

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
                annot.set_text(f"Aspect: {aspect}\nAttribute: {attribute}\nEvent: {event}\nEvent no.: {csv_start+idx*downsample_factor}")
                annot.set_visible(True)
                fig.canvas.draw_idle()
            elif annot.get_visible():
                annot.set_visible(False)
                fig.canvas.draw_idle()
        elif annot.get_visible():
            annot.set_visible(False)
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("button_release_event", hover)
    TIMINGS['plot_finalization'] = time.perf_counter() - step_start

    # Use tight_layout but let the gridspec handle the checkbox area
    plt.tight_layout(rect=(0, 0, 0.8, 1))

    return fig


def render_figure(fig, rendering_mode: RenderingMode, output_path: Path | None = None):
    """
    Render the figure either to a file or to an interactive GUI.

    Args:
        fig: matplotlib.figure.Figure to render
        rendering_mode: RenderingMode enum specifying how to render
        output_path: Optional path for file output (defaults to nesting_levels_plot.png in script dir)
    """
    if rendering_mode == RenderingMode.Gui:
        print("Displaying plot in interactive GUI...")
        plt.show()
    elif rendering_mode == RenderingMode.File:
        if output_path is None:
            output_path = Path(__file__).parent / "nesting_levels_plot.png"
        print(f"Saving plot to: {output_path}")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print("Plot saved successfully!")
    else:
        print(f"Unknown rendering mode: {rendering_mode}")


def print_performance_stats(csv_path: Path, df, nesting_levels, aspect_colors, compute_event_count):
    """
    Print detailed performance and data statistics.

    Args:
        csv_path: Path to the CSV file
        df: The dataframe with trace data
        nesting_levels: Numpy array of nesting levels
        aspect_colors: Dict mapping aspects to colors
        compute_event_count: Number of COMPUTE_BEGIN/COMPUTE_END events
    """
    timestamps = df['timestamp'].values

    # Display detailed timing breakdown
    print("\n" + "="*60)
    print("PERFORMANCE TIMING BREAKDOWN:")
    print("="*60)
    file_size_mb = csv_path.stat().st_size / (1024*1024)
    print(f"CSV Parsing:          {TIMINGS['csv_parsing']:>8.3f}s  ({file_size_mb/TIMINGS['csv_parsing']:>6.1f} MB/s)")
    print(f"Nesting Calculation:  {TIMINGS['nesting_calculation']:>8.3f}s  ({len(df)/TIMINGS['nesting_calculation']:>6.0f} events/s)")
    print(f"Aspect Colors:        {TIMINGS['aspect_colors']:>8.3f}s")
    print(f"Plot Setup:           {TIMINGS['plot_setup']:>8.3f}s")
    print(f"Plotting:             {TIMINGS['plotting']:>8.3f}s")
    print(f"KD-tree Build:        {TIMINGS['kdtree_build']:>8.3f}s")
    print(f"Plot Finalization:    {TIMINGS['plot_finalization']:>8.3f}s")
    print("-" * 60)
    print(f"TOTAL TIME:           {TIMINGS['total']:>8.3f}s")
    print("="*60)

    # Calculate percentages
    print("\nTime Distribution:")
    for step, duration in sorted(TIMINGS.items(), key=lambda x: x[1], reverse=True):
        if step != 'total':
            percentage = (duration / TIMINGS['total']) * 100
            print(f"  {step:.<25} {percentage:>5.1f}%")
    print("="*60 + "\n")

    # Display stats
    max_level = nesting_levels.max() if len(nesting_levels) > 0 else 0
    print("DATA STATISTICS:")
    print("="*60)
    print(f"Maximum nesting level: {max_level}")
    print(f"Total events processed: {len(df):,}")
    print(f"Computation events (BEGIN/END): {compute_event_count:,}")
    print(f"Unique aspects: {len(aspect_colors)}")
    print(f"Time range: {timestamps[-1]:,} ns ({timestamps[-1] / 1e9:.3f} seconds)")
    print(f"File size: {file_size_mb:.2f} MB")
    print("="*60 + "\n")


def plot_computation_nesting(df: DataFrame, csv_path: Path, rendering_mode: RenderingMode, downsample_to: int, csv_start: int):
    """
    Main orchestrator function to plot computation nesting levels.

    Args:
        csv_path: Path to the CSV trace file
        rendering_mode: How to render the plot (GUI or File)
    """
    # Track timing for all major steps
    overall_start = time.perf_counter()

    # Process the data
    result = process_nesting_data(df)
    if result is None:
        return

    (df, timestamps, nesting_levels, event_types, attributes, aspects,
     aspect_colors, compute_event_count, unique_event_types) = result

    # Create the plot
    fig = create_nesting_level_plot(timestamps, nesting_levels, event_types,
                                      aspects, attributes, aspect_colors,
                                      unique_event_types, downsample_to=downsample_to, csv_start=csv_start)

    TIMINGS['total'] = time.perf_counter() - overall_start

    # Print statistics
    print_performance_stats(csv_path, df, nesting_levels, aspect_colors, compute_event_count)

    # Render the plot
    render_figure(fig, rendering_mode)

def main():
    parser = argparse.ArgumentParser(description='Plot computation event nesting levels over time')
    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to the CSV log file (default: log.csv in script directory)',
    )
    parser.add_argument(
        '--rendering_mode',
        default=RenderingMode.Gui,
        type=RenderingMode,
        choices=list(RenderingMode),
        help='How this script should render the graphs, to a file, or to an interactive gui',
    )
    parser.add_argument(
        '--downsample_to',
        default=10000,
        type=int,
        help='Target sample points. Use non-positive values to run without downsampling',
    )
    parser.add_argument(
        '--start',
        default=0,
        type=int,
        help='First event to read from csv'
    )
    parser.add_argument(
        '--end',
        default=-1,
        type=int,
        help='Last event to read from csv. Use negative values for last value in the csv'
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    rendering_mode = args.rendering_mode
    downsample_to = args.downsample_to
    csv_start = args.start
    csv_end = args.end

    print(f"csv_path: {csv_path }")
    print(f"rendering_mode: {rendering_mode }")
    print(f"downsample_to: {downsample_to }")

    df = read_csv_to_dataframe(csv_path, csv_start, csv_end)

    if df.empty:
        print("No events found in the log file.")
        return None

    plot_computation_nesting(df, csv_path, rendering_mode, downsample_to, csv_start)


if __name__ == "__main__":
    main()

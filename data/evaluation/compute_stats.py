import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import time
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

############################################################
# Column name constants
############################################################

DfTimestamp = "timestamp"
DfAspect = "aspect"
DfAstNodeId = "astNodeId"
DfAstNodeName = "astNodeName"
DfAttribute = "attribute"
DfEventName = "eventName"

############################################################
# Main compute functions
############################################################

def read_csv_to_dataframe(csv_path: Path) -> pd.DataFrame:
    """Read CSV trace file into DataFrame."""
    logger.info(f"Reading CSV file: {csv_path}")
    step_start = time.perf_counter()

    names = [
        "timestamp",
        "aspect",
        "astNodeId",
        "astNodeName",
        "attribute",
        "eventName",
    ]
    df = pd.read_csv(
        csv_path,
        sep="\t",
        header=None,
        names=names,
        dtype={"aspect": str, "astNodeName": str, "attribute": str, "eventName": str},
    )

    elapsed = time.perf_counter() - step_start
    logger.info(f"Loaded {len(df):,} total events from CSV (took {elapsed:.3f}s)")

    return df


def create_attributes_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a DataFrame with one row per unique (aspect, attribute) pair.

    Args:
        df: Input trace log DataFrame

    Returns:
        DataFrame with 'aspect' and 'attribute' columns
    """
    # Get unique (aspect, attribute) pairs
    attributes_df = df[[DfAspect, DfAttribute]].drop_duplicates().copy()

    # Sort by aspect then attribute for consistent ordering
    attributes_df = attributes_df.sort_values([DfAspect, DfAttribute]).reset_index(drop=True)

    return attributes_df


def compute_compute_event_metrics(df: pd.DataFrame, attributes_df: pd.DataFrame) -> None:
    """
    Add performance metric columns to attributes_df (modifies in-place).

    Columns added:
    - mean_time: Mean computation time (μs)
    - median_time: Median computation time (μs)
    - p95_time: 95th percentile (μs)
    - p99_time: 99th percentile (μs)
    - total_time: Total time spent (μs)
    - min_time: Minimum time (μs)
    - max_time: Maximum time (μs)

    Args:
        df: Input trace log DataFrame
        attributes_df: DataFrame to modify (has 'attribute' column)
    """
    logger.info("Computing performance metrics...")
    step_start = time.perf_counter()

    # Filter compute events (vectorized boolean indexing)
    compute_events = df[df[DfEventName].isin(['COMPUTE_BEGIN', 'COMPUTE_END'])].copy()

    if compute_events.empty:
        logger.warning("No compute events found - skipping performance metrics")
        # Add empty columns
        for col in ['mean_time', 'median_time', 'p95_time', 'p99_time',
                    'total_time', 'min_time', 'max_time']:
            attributes_df[col] = np.nan
        return

    # Create node-level key for pairing BEGIN/END events
    compute_events['node_attr_key'] = (compute_events[DfAstNodeId].astype(str) + "_" +
                                       compute_events[DfAspect] + "." +
                                       compute_events[DfAttribute])

    # Separate begins and ends (vectorized)
    begins = compute_events[compute_events[DfEventName] == 'COMPUTE_BEGIN'].copy()
    ends = compute_events[compute_events[DfEventName] == 'COMPUTE_END'].copy()

    if begins.empty or ends.empty:
        logger.warning("Missing BEGIN or END events - skipping performance metrics")
        for col in ['mean_time', 'median_time', 'p95_time', 'p99_time',
                    'total_time', 'min_time', 'max_time']:
            attributes_df[col] = np.nan
        return

    # Pair by node_attr_key using vectorized groupby + cumcount
    begins['seq'] = begins.groupby('node_attr_key').cumcount()
    ends['seq'] = ends.groupby('node_attr_key').cumcount()

    # Vectorized merge to pair events
    paired = begins.merge(ends, on=['node_attr_key', 'seq'], suffixes=('_begin', '_end'))

    if paired.empty:
        logger.warning("Could not pair BEGIN/END events - skipping performance metrics")
        for col in ['mean_time', 'median_time', 'p95_time', 'p99_time',
                    'total_time', 'min_time', 'max_time']:
            attributes_df[col] = np.nan
        return

    # Vectorized duration calculation
    paired['duration'] = paired[DfTimestamp + '_end'] - paired[DfTimestamp + '_begin']

    # Vectorized aggregation per (aspect, attribute) using built-in pandas functions
    stats = paired.groupby([DfAspect + '_begin', DfAttribute + '_begin'])['duration'].agg([
        ('mean_time', 'mean'),
        ('median_time', 'median'),
        ('p95_time', lambda x: x.quantile(0.95)),
        ('p99_time', lambda x: x.quantile(0.99)),
        ('total_time', 'sum'),
        ('min_time', 'min'),
        ('max_time', 'max')
    ]).reset_index()

    # Convert to microseconds (vectorized)
    time_cols = ['mean_time', 'median_time', 'p95_time', 'p99_time', 'total_time', 'min_time', 'max_time']
    stats[time_cols] = stats[time_cols] / 1000

    # Rename columns for merging
    stats.rename(columns={DfAspect + '_begin': DfAspect, DfAttribute + '_begin': DfAttribute}, inplace=True)

    # Vectorized merge into attributes_df
    merge_cols = [DfAspect, DfAttribute, 'mean_time', 'median_time', 'p95_time',
                  'p99_time', 'total_time', 'min_time', 'max_time']

    temp_df = attributes_df.merge(
        stats[merge_cols],
        on=[DfAspect, DfAttribute],
        how='left'
    )

    # Copy columns back to attributes_df (in-place modification)
    for col in ['mean_time', 'median_time', 'p95_time', 'p99_time',
                'total_time', 'min_time', 'max_time']:
        attributes_df[col] = temp_df[col].fillna(0.0).astype(float)

    elapsed = time.perf_counter() - step_start
    logger.info(f"Performance metrics computed in {elapsed:.3f}s")

def compute_cache_metrics(df: pd.DataFrame, attributes_df: pd.DataFrame) -> None:
    """
    Add cache metric columns to attributes_df (modifies in-place).

    Analyzes write-read blocks: sequences of (WRITE, READ, READ, ...) until next WRITE.
    Block size = number of reads before the next write (or end of sequence).

    Columns added:
    - cache_writes (N_CACHE_WRITES): Total number of CACHE_WRITE events
    - cache_reads (N_CACHE_READS): Total number of CACHE_READ events
    - num_unique_block_types: Number of different block sizes observed
    - min_block_size: Minimum block size (fewest reads in any block)
    - max_block_size: Maximum block size (most reads in any block)
    - median_block_size: Median block size (50th percentile)
    - mean_block_size: Mean block size (average reads per write)
    - total_blocks: Total number of blocks

    Args:
        df: Input trace log DataFrame
        attributes_df: DataFrame to modify (has 'attribute' column)
    """
    logger.info("Computing cache metrics...")
    step_start = time.perf_counter()

    # Filter cache events (vectorized boolean indexing)
    cache_events = df[df[DfEventName].isin(['CACHE_READ', 'CACHE_WRITE'])].copy()

    if cache_events.empty:
        logger.warning("No cache events found - skipping cache metrics")
        # Add empty columns
        for col in ['cache_writes', 'cache_reads',
                    'num_unique_block_types', 'min_block_size', 'max_block_size',
                    'median_block_size', 'mean_block_size', 'total_blocks']:
            attributes_df[col] = np.nan
        return

    # Create node-level key for tracking blocks per (node, aspect, attribute)
    cache_events['node_attr_key'] = (cache_events[DfAstNodeId].astype(str) + "_" +
                                     cache_events[DfAspect] + "." +
                                     cache_events[DfAttribute])

    # Sort by timestamp for chronological order (vectorized)
    cache_events = cache_events.sort_values(DfTimestamp).reset_index(drop=True)

    # Identify blocks using vectorized operations:
    # A block starts with each WRITE event. Block ID = cumulative count of WRITEs
    cache_events['is_write'] = (cache_events[DfEventName] == 'CACHE_WRITE').astype(int)
    cache_events['is_read'] = (cache_events[DfEventName] == 'CACHE_READ').astype(int)

    # Group by (node_attr_key) and assign block IDs using cumsum of writes
    cache_events['block_id'] = cache_events.groupby('node_attr_key')['is_write'].cumsum()

    # Now for each block, count the number of reads
    # Filter to only reads (block size = count of reads in that block)
    reads_in_blocks = cache_events[cache_events['is_read'] == 1].copy()

    # Group by (node_attr_key, block_id) and count reads per block
    block_sizes_per_node = reads_in_blocks.groupby(['node_attr_key', 'block_id']).size().reset_index(name='block_size')

    # Also include blocks with 0 reads (writes with no following reads)
    # Find all blocks (every write creates a block)
    all_blocks_nodes = cache_events[cache_events['is_write'] == 1][['node_attr_key', DfAspect, DfAttribute, 'block_id']].copy()

    if all_blocks_nodes.empty:
        logger.warning("No write events found - skipping cache metrics")
        for col in ['cache_writes', 'cache_reads',
                    'num_unique_block_types', 'min_block_size', 'max_block_size',
                    'median_block_size', 'mean_block_size', 'total_blocks']:
            attributes_df[col] = np.nan
        return

    # Merge block sizes (left join to include blocks with 0 reads)
    all_blocks_nodes = all_blocks_nodes.merge(
        block_sizes_per_node,
        on=['node_attr_key', 'block_id'],
        how='left'
    )
    all_blocks_nodes['block_size'] = all_blocks_nodes['block_size'].fillna(0).astype(int)

    logger.debug(f"Analyzed {len(all_blocks_nodes)} total cache blocks")

    # Aggregate block statistics per (aspect, attribute) (pooled across all nodes) - fully vectorized
    stats = all_blocks_nodes.groupby([DfAspect, DfAttribute])['block_size'].agg([
        ('total_blocks', 'count'),
        ('num_unique_block_types', lambda x: x.nunique()),
        ('min_block_size', 'min'),
        ('max_block_size', 'max'),
        ('median_block_size', 'median'),
        ('mean_block_size', 'mean')
    ]).reset_index()

    logger.debug(f"Computed block statistics for {len(stats)} (aspect, attribute) pairs")

    # Debug: Show sample aspect/attribute pairs from stats
    if len(stats) > 0:
        logger.debug(f"Sample stats (aspect, attribute): ({stats.iloc[0][DfAspect]}, {stats.iloc[0][DfAttribute]})")

    # Count total reads and writes per (aspect, attribute) (vectorized)
    reads_count = cache_events.groupby([DfAspect, DfAttribute])['is_read'].sum().reset_index()
    writes_count = cache_events.groupby([DfAspect, DfAttribute])['is_write'].sum().reset_index()

    # Merge counts into stats
    stats = stats.merge(reads_count, on=[DfAspect, DfAttribute], how='left')
    stats = stats.merge(writes_count, on=[DfAspect, DfAttribute], how='left')

    stats.rename(columns={'is_read': 'cache_reads', 'is_write': 'cache_writes'}, inplace=True)
    stats['cache_reads'] = stats['cache_reads'].fillna(0).astype(int)
    stats['cache_writes'] = stats['cache_writes'].fillna(0).astype(int)

    logger.debug(f"Merging cache stats into {len(attributes_df)} attributes")
    logger.debug(f"Stats dataframe has {len(stats)} rows")

    # Debug: Show sample of stats
    if len(stats) > 0:
        logger.debug(f"Sample stats row: {stats.iloc[0].to_dict()}")

    # Vectorized merge into attributes_df (same pattern as performance metrics)
    merge_cols = ['cache_writes', 'cache_reads',  'num_unique_block_types',
                  'min_block_size', 'max_block_size', 'median_block_size', 'mean_block_size', 'total_blocks']

    temp_df = attributes_df.merge(
        stats[[DfAspect, DfAttribute] + merge_cols],
        on=[DfAspect, DfAttribute],
        how='left'
    )

    logger.debug(f"After merge, temp_df has {len(temp_df)} rows")
    logger.debug(f"Non-null cache_writes in temp_df: {temp_df['cache_writes'].notna().sum()}")

    # Copy columns back to attributes_df (in-place modification)
    for col in merge_cols:
        attributes_df[col] = temp_df[col].fillna(0).values
    logger.debug(f"Non-null cache_writes in attributes_df: {attributes_df['cache_writes'].notna().sum()}")

    elapsed = time.perf_counter() - step_start
    logger.info(f"Cache metrics computed in {elapsed:.3f}s")


def compute_event_counts_metrics(df: pd.DataFrame, attributes_df: pd.DataFrame) -> None:
    """
    Add event type count columns to attributes_df (modifies in-place).

    For each event type, adds a column with the count of that event for each attribute.
    Column names will be the event type name (e.g., 'COMPUTE_BEGIN', 'CACHE_READ', etc.)

    Args:
        df: Input trace log DataFrame
        attributes_df: DataFrame to modify (has 'aspect' and 'attribute' columns)
    """
    logger.info("Computing event type counts per attribute...")
    step_start = time.perf_counter()

    # Count events by (aspect, attribute, eventName) using vectorized groupby
    event_counts_series = df.groupby([DfAspect, DfAttribute, DfEventName], observed=True).size()
    event_counts = event_counts_series.to_frame(name='count').reset_index()

    # Pivot to get event types as columns (vectorized operation)
    event_pivot = event_counts.pivot_table(
        index=[DfAspect, DfAttribute],
        columns=DfEventName,
        values='count',
        fill_value=0
    ).reset_index()

    # Get all event type columns (excluding aspect and attribute)
    event_type_cols = [col for col in event_pivot.columns if col not in [DfAspect, DfAttribute]]

    logger.debug(f"Found {len(event_type_cols)} unique event types: {event_type_cols}")

    # Merge into attributes_df
    temp_df = attributes_df.merge(
        event_pivot,
        on=[DfAspect, DfAttribute],
        how='left'
    )


    # Copy event count columns back to attributes_df (in-place modification)
    # Fill NaN with 0 for attributes that don't have certain event types
    for col in event_type_cols:
        attributes_df[col] = temp_df[col].fillna(0).astype(int)

    # out of the event counts we compute the ratio of the reads over all the "attribute calls" (cache reads + compute begins)
    attributes_df["CACHE_READ_CALL_RATIO"] = attributes_df["CACHE_READ"] / (attributes_df["COMPUTE_BEGIN"] + attributes_df["CACHE_READ"])

    elapsed = time.perf_counter() - step_start
    logger.info(f"Event type counts computed in {elapsed:.3f}s")


def compute_metrics(df: pd.DataFrame, compute_performance: bool = True,
                   compute_cache: bool = True, compute_event_counts: bool = True) -> Dict[str, Any]:
    """
    Process trace data and compute all metrics.

    Args:
        df: Input trace log DataFrame
        compute_performance: Whether to compute performance metrics
        compute_cache: Whether to compute cache metrics
        compute_event_counts: Whether to compute event type counts per attribute

    Returns:
        Dictionary containing:
        - 'attributes': DataFrame with per-attribute metrics (one row per attribute)
        - 'global': Dictionary with global metrics (total counts, etc.)
    """
    logger.info(f"Processing {len(df):,} events...")
    overall_start = time.perf_counter()

    # Create base attributes DataFrame (one row per unique attribute)
    logger.debug("Creating attributes dataframe...")
    attributes_df = create_attributes_dataframe(df)
    logger.info(f"Found {len(attributes_df)} unique (aspect, attribute) pairs")

    # Debug: Show sample aspect/attribute pairs
    if len(attributes_df) > 0:
        logger.debug(f"Sample attributes_df (aspect, attribute): ({attributes_df.iloc[0][DfAspect]}, {attributes_df.iloc[0][DfAttribute]})")

    # Each metric function adds columns to attributes_df
    if compute_performance:
        compute_compute_event_metrics(df, attributes_df)

    if compute_cache:
        compute_cache_metrics(df, attributes_df)

    if compute_event_counts:
        compute_event_counts_metrics(df, attributes_df)

    # Compute global metrics separately
    logger.debug("Computing global metrics...")

    # Count all event types using vectorized pandas methods
    event_counts = df[DfEventName].value_counts().reset_index()
    event_counts.columns = ['event_name', 'count']
    event_counts = event_counts.sort_values('count', ascending=False)

    # Count unique aspects, attributes, and node names
    unique_aspects = df[DfAspect].nunique()
    unique_attributes = df[DfAttribute].nunique()
    unique_node_names = df[DfAstNodeName].nunique()

    # Count how many attributes have cache data
    if compute_cache and 'cache_writes' in attributes_df.columns:
        cached_attributes_count = attributes_df['cache_writes'].notna().sum()
    else:
        cached_attributes_count = 0

    global_metrics = {
        'total_events': len(df),
        'unique_aspects': unique_aspects,
        'unique_attributes': unique_attributes,
        'unique_aspect_attribute_pairs': len(attributes_df),
        'unique_node_names': unique_node_names,
        'total_compute_events': len(df[df[DfEventName].isin(['COMPUTE_BEGIN', 'COMPUTE_END'])]),
        'total_cache_events': len(df[df[DfEventName].isin(['CACHE_READ', 'CACHE_WRITE'])]),
        'total_token_reads': len(df[df[DfEventName] == 'TOKEN_READ']),
        'attributes_with_cache_data': cached_attributes_count,
        'event_counts': event_counts,
    }

    elapsed = time.perf_counter() - overall_start
    logger.info(f"All metrics computed in {elapsed:.3f}s")

    return {
        'attributes': attributes_df,
        'global': global_metrics
    }


def display_attribute_table(attributes_df: pd.DataFrame, sort_by: str, title: str,
                           top_n: int = 20, ascending: bool = False,
                           filter_func=None, columns=None) -> None:
    """
    Display a formatted table of attribute metrics sorted by a specific column.

    Args:
        attributes_df: DataFrame with attribute metrics
        sort_by: Column name to sort by
        title: Title to display above the table
        top_n: Number of rows to display (default 20)
        ascending: Sort order (default False for descending)
        filter_func: Optional function to filter rows (e.g., lambda df: df[df['cache_writes'].notna()])
        columns: Optional list of column names to display (None = all columns)
    """
    logger.debug(f"Displaying table: {title}, sorted by {sort_by}")

    # Apply filter if provided
    if filter_func is not None:
        display_df = filter_func(attributes_df).copy()
        if display_df.empty:
            logger.warning(f"No data to display for: {title}")
            return
    else:
        display_df = attributes_df.copy()

    # Sort by specified column
    if sort_by in display_df.columns:
        display_df = display_df.sort_values(sort_by, ascending=ascending, na_position='last').head(top_n)
    else:
        logger.warning(f"Sort column '{sort_by}' not found, showing first {top_n} rows")
        display_df = display_df.head(top_n)

    # Select specific columns if provided
    if columns is not None:
        # Only include columns that exist
        columns = [col for col in columns if col in display_df.columns]
        display_df = display_df[columns]

    # Round float columns for better display
    float_cols = display_df.select_dtypes(include=['float64']).columns
    for col in float_cols:
        display_df[col] = display_df[col].round(4)

    # Print the table
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(display_df.to_string(index=False))
    print("=" * 80)

    # Print summary info
    total_count = len(filter_func(attributes_df)) if filter_func else len(attributes_df)
    print(f"Showing top {len(display_df)} of {total_count} attributes")


def present_results(metrics: Dict[str, Any], csv_path: Path) -> None:
    """
    Print results to console in formatted tables.

    Args:
        metrics: Dict with 'attributes' (DataFrame) and 'global' (dict) keys
        csv_path: Path to input CSV (for context)
    """
    logger.debug("Preparing results for display...")
    attributes_df = metrics['attributes']
    global_metrics = metrics['global']

    # Print global metrics (excluding the event_counts dataframe)
    print("\n" + "=" * 60)
    print("GLOBAL METRICS:")
    print("=" * 60)
    for key, value in global_metrics.items():
        if key != 'event_counts':  # Skip the dataframe
            print(f"  {key:.<40} {value:>15,}")
    print("=" * 60)

    # Print event type counts
    if 'event_counts' in global_metrics:
        event_counts_df = global_metrics['event_counts']
        print("\n" + "=" * 60)
        print("EVENT TYPE COUNTS:")
        print("=" * 60)
        print(event_counts_df.to_string(index=False))
        print("=" * 60)

    # Display per-attribute metrics sorted by different criteria

    # 2. Sort by total time (performance - attributes consuming most time)
    if 'total_time' in attributes_df.columns:
        display_attribute_table(
            attributes_df,
            sort_by='total_time',
            title='PER-ATTRIBUTE METRICS: Top by Total Computation Time',
            top_n=20,
            ascending=False
        )

    # 3. Sort by cache reads per write ratio (cache efficiency)
    if 'mean_block_size' in attributes_df.columns:
        display_attribute_table(
            attributes_df,
            sort_by='mean_block_size',
            title='PER-ATTRIBUTE METRICS: Top by Cache Read/Write Ratio (Cache Efficiency)',
            top_n=20,
            ascending=True,
            filter_func=lambda df: df[df['cache_writes'].notna()]
        )

    if 'mean_block_size' in attributes_df.columns:
        display_attribute_table(
            attributes_df,
            sort_by='mean_block_size',
            title='PER-ATTRIBUTE METRICS: Top by Cache Read/Write Ratio (Cache Efficiency)',
            top_n=20,
            ascending=True,
            filter_func=lambda df: df[df['cache_writes'].notna()]
        )

    if 'CACHE_READ_CALL_RATIO' in attributes_df.columns:
        display_attribute_table(
            attributes_df,
            sort_by='CACHE_READ_CALL_RATIO',
            title='PER-ATTRIBUTE METRICS: Top by cache reads over all attribute calls',
            top_n=20,
            ascending=True,
            filter_func=lambda df: df[df['cache_reads'] > 0]
        )



DESC = """
Examples:
  python compute_stats.py trace-log.csv
  python compute_stats.py path/to/trace.csv

This script computes:
  - Performance metrics (computation time, slowest attributes)
  - Cache effectiveness (hit rates, optimization targets)
  - Circular evaluation statistics
  - Computation patterns (recomputation, token reads, flushes)
  - Temporal patterns (activity over time)
  - Outlier detection and optimization recommendations
"""


def main():
    """Main entry point for the trace analysis script."""
    parser = argparse.ArgumentParser(
        description="Compute comprehensive metrics from attribute grammar trace data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DESC,
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to the CSV trace log file",
    )

    # Metric selection flags
    parser.add_argument('--performance', action='store_true',
                       help='Compute performance metrics only')
    parser.add_argument('--cache', action='store_true',
                       help='Compute cache metrics only')
    parser.add_argument('--no-event-counts', action='store_true',
                       help='Skip computing per-attribute event type counts')

    # Logging configuration
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose (DEBUG) logging')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Show only warnings and errors')

    args = parser.parse_args()

    # Configure logging based on verbosity flags
    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    csv_path = Path(args.csv_file)

    if not csv_path.exists():
        logger.error(f"File not found: {csv_path}")
        return 1

    logger.info(f"Analyzing trace file: {csv_path}")

    # Read the data
    df = read_csv_to_dataframe(csv_path)

    if df.empty:
        logger.error("No events found in the log file.")
        return 1

    # Determine which metrics to compute
    compute_all = not (args.performance or args.cache)

    if args.performance:
        logger.debug("Computing performance metrics only")
    elif args.cache:
        logger.debug("Computing cache metrics only")
    else:
        logger.debug("Computing all metrics")

    # Event counts are computed by default unless --no-event-counts is specified
    compute_event_counts = not args.no_event_counts

    # Compute metrics
    metrics = compute_metrics(
        df,
        compute_performance=compute_all or args.performance,
        compute_cache=compute_all or args.cache,
        compute_event_counts=compute_event_counts
    )

    attributes_df = metrics['attributes']

    output_file = "compute_stats_result.csv"
    logger.info(f"writing to file: {output_file}")
    attributes_df.to_csv(output_file, sep="\t")

    # Present results
    # present_results(metrics, csv_path)

    logger.info("Analysis complete")
    return 0


if __name__ == "__main__":
    main()

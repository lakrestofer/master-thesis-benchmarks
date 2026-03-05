import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import time
from typing import Dict, Any

############################################################
# Main compute functions
############################################################

def read_csv_to_dataframe(csv_path: Path) -> pd.DataFrame:
    """Read CSV trace file into DataFrame."""
    print(f"Reading CSV file: {csv_path}")
    step_start = time.perf_counter()

    names = ['timestamp', 'aspect', 'astNodeId', 'astNodeName', 'attribute', 'eventName']
    df = pd.read_csv(csv_path, sep='\t', header=None, names=names, dtype={'aspect': str, 'astNodeName': str, 'attribute': str, 'eventName': str})

    elapsed = time.perf_counter() - step_start
    print(f"Loaded {len(df):,} total events from CSV (took {elapsed:.3f}s)")

    return df


def compute_performance_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute performance metrics from COMPUTE_BEGIN/END pairs."""
    print("\nComputing performance metrics...")
    step_start = time.perf_counter()

    # Filter to only compute events
    compute_df = df[df['eventName'].isin(['COMPUTE_BEGIN', 'COMPUTE_END'])].copy()

    if compute_df.empty:
        print("  No COMPUTE_BEGIN/END pairs found")
        return {}

    # Vectorized pairing using groupby and cumulative indexing
    # For each (aspect, attribute, astNodeId), assign a pair_id to match BEGIN/END
    compute_df = compute_df.sort_values('timestamp')
    compute_df['is_begin'] = (compute_df['eventName'] == 'COMPUTE_BEGIN').astype(int)

    # Group by key and assign pair IDs using cumulative sum
    compute_df['pair_id'] = compute_df.groupby(['aspect', 'attribute', 'astNodeId'])['is_begin'].cumsum()

    # Split into BEGIN and END dataframes
    begin_df = compute_df[compute_df['eventName'] == 'COMPUTE_BEGIN'].copy()
    end_df = compute_df[compute_df['eventName'] == 'COMPUTE_END'].copy()

    # Merge on the pairing key
    merged = pd.merge(
        begin_df[['aspect', 'attribute', 'astNodeId', 'pair_id', 'timestamp']],
        end_df[['aspect', 'attribute', 'astNodeId', 'pair_id', 'timestamp']],
        on=['aspect', 'attribute', 'astNodeId', 'pair_id'],
        suffixes=('_begin', '_end')
    )

    # Calculate durations
    merged['duration'] = merged['timestamp_end'] - merged['timestamp_begin']
    durations_df = merged[['aspect', 'attribute', 'astNodeId', 'duration']].copy()

    # Per-aspect statistics
    aspect_stats = durations_df.groupby('aspect')['duration'].agg([
        ('count', 'count'),
        ('total_time', 'sum'),
        ('mean', 'mean'),
        ('median', 'median'),
        ('p95', lambda x: np.percentile(x, 95)),
        ('p99', lambda x: np.percentile(x, 99)),
        ('max', 'max')
    ]).reset_index()

    total_time = aspect_stats['total_time'].sum()
    aspect_stats['pct_total'] = (aspect_stats['total_time'] / total_time * 100)
    aspect_stats = aspect_stats.sort_values('total_time', ascending=False)

    # Per-attribute statistics
    attr_stats = durations_df.groupby(['aspect', 'attribute'])['duration'].agg([
        ('count', 'count'),
        ('total_time', 'sum'),
        ('mean', 'mean'),
        ('median', 'median'),
        ('p95', lambda x: np.percentile(x, 95)),
        ('p99', lambda x: np.percentile(x, 99)),
        ('max', 'max')
    ]).reset_index()

    attr_stats['pct_total'] = (attr_stats['total_time'] / total_time * 100)

    # Top lists
    top_slowest_total = attr_stats.nlargest(20, 'total_time')
    top_slowest_mean = attr_stats.nlargest(20, 'mean')
    top_frequent = attr_stats.nlargest(20, 'count')

    # Histogram bins (log scale)
    hist, bin_edges = np.histogram(durations_df['duration'], bins=50)

    elapsed = time.perf_counter() - step_start
    print(f"  Computed performance metrics in {elapsed:.3f}s")

    return {
        'aspect_stats': aspect_stats,
        'attr_stats': attr_stats,
        'top_slowest_total': top_slowest_total,
        'top_slowest_mean': top_slowest_mean,
        'top_frequent': top_frequent,
        'histogram': (hist, bin_edges),
        'total_time': total_time,
        'durations_df': durations_df
    }

def process_nesting_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Process trace data and compute all metrics.

    Returns:
        Dictionary containing all computed metrics
    """
    print(f"\nProcessing {len(df):,} events...")
    overall_start = time.perf_counter()

    metrics = {}

    # Compute all metric categories
    metrics['performance'] = compute_performance_metrics(df)

    # Overall statistics
    metrics['overall'] = {
        'total_events': len(df),
        'unique_aspects': df['aspect'].nunique(),
        'unique_attributes': df.groupby(['aspect', 'attribute']).ngroups,
        'time_range': df['timestamp'].max() - df['timestamp'].min(),
        'event_type_distribution': df['eventName'].value_counts().to_dict()
    }

    elapsed = time.perf_counter() - overall_start
    print(f"\nAll metrics computed in {elapsed:.3f}s")

    return metrics


def present_results(metrics: Dict[str, Any], csv_path: Path) -> None:
    """Print formatted results to console."""

    print("\n" + "="*80)
    print(" "*20 + "TRACE ANALYSIS RESULTS")
    print("="*80)

    # Section 1: Overall Statistics
    print("\n" + "="*80)
    print("SECTION 1: OVERALL STATISTICS")
    print("="*80)

    overall = metrics['overall']
    print(f"Total events:           {overall['total_events']:>15,}")
    print(f"Unique aspects:         {overall['unique_aspects']:>15,}")
    print(f"Unique attributes:      {overall['unique_attributes']:>15,}")
    print(f"Time range:             {overall['time_range']:>15,} ns ({overall['time_range']/1e9:.3f}s)")

    file_size_mb = csv_path.stat().st_size / (1024*1024)
    print(f"File size:              {file_size_mb:>15.2f} MB")

    print("\nEvent Type Distribution:")
    event_dist = overall['event_type_distribution']
    total_events = overall['total_events']
    for event_type in sorted(event_dist.keys(), key=lambda x: event_dist[x], reverse=True):
        count = event_dist[event_type]
        pct = count / total_events * 100
        print(f"  {event_type:<25} {count:>12,} ({pct:>6.2f}%)")

    # Section 2: Performance Metrics
    if metrics['performance']:
        print("\n" + "="*80)
        print("SECTION 2: PERFORMANCE METRICS")
        print("="*80)

        perf = metrics['performance']
        total_time = perf['total_time']

        print(f"\nTotal computation time: {total_time:,} ns ({total_time/1e9:.3f}s)")

        print("\nPer-Aspect Computation Statistics (Top 15 by total time):")
        print(f"{'Aspect':<30} {'Count':>10} {'Total (ms)':>12} {'Mean (μs)':>12} {'Median (μs)':>12} {'P95 (μs)':>12} {'% Total':>10}")
        print("-" * 130)

        for _, row in perf['aspect_stats'].head(15).iterrows():
            print(f"{row['aspect']:<30} {int(row['count']):>10,} {row['total_time']/1e6:>12.2f} "
                  f"{row['mean']/1e3:>12.2f} {row['median']/1e3:>12.2f} {row['p95']/1e3:>12.2f} "
                  f"{row['pct_total']:>9.2f}%")

        print("\nTop 20 Slowest Attributes by Total Time:")
        print(f"{'Aspect':<30} {'Attribute':<45} {'Count':>10} {'Total (ms)':>12} {'Mean (μs)':>12} {'%':>8}")
        print("-" * 130)

        for _, row in perf['top_slowest_total'].head(20).iterrows():
            aspect = str(row['aspect'])[:30]
            attribute = str(row['attribute'])[:45]
            print(f"{aspect:<30} {attribute:<45} {int(row['count']):>10,} "
                  f"{row['total_time']/1e6:>12.2f} {row['mean']/1e3:>12.2f} {row['pct_total']:>7.2f}%")

        print("\nTop 20 Slowest Attributes by Average Time:")
        print(f"{'Aspect':<30} {'Attribute':<45} {'Count':>10} {'Mean (μs)':>14} {'Max (μs)':>14}")
        print("-" * 125)

        for _, row in perf['top_slowest_mean'].head(20).iterrows():
            aspect = str(row['aspect'])[:30]
            attribute = str(row['attribute'])[:45]
            print(f"{aspect:<30} {attribute:<45} {int(row['count']):>10,} "
                  f"{row['mean']/1e3:>14.2f} {row['max']/1e3:>14.2f}")

        print("\nTop 20 Most Frequently Computed Attributes:")
        print(f"{'Aspect':<30} {'Attribute':<45} {'Count':>10} {'Total (ms)':>14} {'Mean (μs)':>14}")
        print("-" * 125)

        for _, row in perf['top_frequent'].head(20).iterrows():
            aspect = str(row['aspect'])[:30]
            attribute = str(row['attribute'])[:45]
            print(f"{aspect:<30} {attribute:<45} {int(row['count']):>10,} "
                  f"{row['total_time']/1e6:>14.2f} {row['mean']/1e3:>14.2f}")

    # # Section 3: Cache Effectiveness
    # if metrics['cache']:
    #     print("\n" + "="*80)
    #     print("SECTION 3: CACHE EFFECTIVENESS")
    #     print("="*80)

    #     cache = metrics['cache']

    #     if not cache['per_aspect'].empty:
    #         print("\nPer-Aspect Cache Statistics:")
    #         print(f"{'Aspect':<30} {'Reads':>10} {'Writes':>10} {'Computes':>10} {'Hit Rate':>10}")
    #         print("-" * 80)

    #         for _, row in cache['per_aspect'].head(15).iterrows():
    #             print(f"{row['aspect']:<30} {int(row['CACHE_READ']):>10,} {int(row['CACHE_WRITE']):>10,} "
    #                   f"{int(row['COMPUTE_BEGIN']):>10,} {row['hit_rate']:>9.2f}%")

    #     if not cache['top_best'].empty:
    #         print("\nTop 20 Best Cached Attributes (Highest Hit Rate):")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Reads':>12} {'Computes':>12} {'Hit Rate':>10}")
    #         print("-" * 120)

    #         for _, row in cache['top_best'].head(20).iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {int(row['CACHE_READ']):>12,} "
    #                   f"{int(row['COMPUTE_BEGIN']):>12,} {row['hit_rate']:>9.2f}%")

    #     if not cache['top_worst'].empty:
    #         print("\nTop 20 Worst Cached Attributes (Lowest Hit Rate):")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Reads':>12} {'Computes':>12} {'Hit Rate':>10}")
    #         print("-" * 120)

    #         for _, row in cache['top_worst'].head(20).iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {int(row['CACHE_READ']):>12,} "
    #                   f"{int(row['COMPUTE_BEGIN']):>12,} {row['hit_rate']:>9.2f}%")

    #     if not cache['optimization_targets'].empty:
    #         print("\nTop 20 Optimization Targets (High Compute, Low Cache):")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Computes':>12} {'Hit Rate':>10} {'Efficiency':>12}")
    #         print("-" * 125)

    #         for _, row in cache['optimization_targets'].head(20).iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {int(row['COMPUTE_BEGIN']):>12,} "
    #                   f"{row['hit_rate']:>9.2f}% {row['efficiency_score']:>11.2f}")

    # Section 4: Circular Attribute Metrics
    # if metrics['circular'] and metrics['circular'].get('case_distribution'):
    #     print("\n" + "="*80)
    #     print("SECTION 4: CIRCULAR ATTRIBUTE METRICS")
    #     print("="*80)

    #     circ = metrics['circular']

    #     print("\nCircular Case Distribution:")
    #     total_circular = sum(circ['case_distribution'].values())
    #     for case_type in sorted(circ['case_distribution'].keys()):
    #         count = circ['case_distribution'][case_type]
    #         pct = count / total_circular * 100 if total_circular > 0 else 0
    #         print(f"  {case_type:<15} {count:>10,} ({pct:>6.2f}%)")

    #     if not circ['circular_evals_df'].empty and not circ['top_expensive'].empty:
    #         print("\nTop 20 Most Expensive Circular Evaluations (by duration):")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Duration (μs)':>16} {'Iterations':>12}")
    #         print("-" * 115)

    #         for _, row in circ['top_expensive'].head(20).iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {row['duration']/1e3:>16.2f} {int(row['iterations']):>12,}")

    #     if not circ['circular_evals_df'].empty and not circ['top_iterations'].empty:
    #         print("\nTop 20 Circular Attributes by Iteration Count:")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Iterations':>12} {'Duration (μs)':>16}")
    #         print("-" * 115)

    #         for _, row in circ['top_iterations'].head(20).iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {int(row['iterations']):>12,} {row['duration']/1e3:>16.2f}")

    # Section 5: Computation Patterns
    # if metrics['patterns']:
    #     print("\n" + "="*80)
    #     print("SECTION 5: COMPUTATION PATTERNS")
    #     print("="*80)

    #     patterns = metrics['patterns']

    #     if not patterns['recomputation'].empty:
    #         print("\nRecomputation Analysis (Top 15):")
    #         print(f"{'Aspect':<30} {'Attribute':<45} {'Unique Nodes':>15} {'Avg/Node':>12} {'Max':>10}")
    #         print("-" * 125)

    #         for _, row in patterns['recomputation'].nlargest(15, 'max_computes').iterrows():
    #             aspect = str(row['aspect'])[:30]
    #             attribute = str(row['attribute'])[:45]
    #             print(f"{aspect:<30} {attribute:<45} {int(row['unique_nodes']):>15,} "
    #                   f"{row['avg_computes_per_node']:>12.2f} {int(row['max_computes']):>10,}")

    #     if not patterns['token_reads'].empty:
    #         print("\nToken Read Statistics by Aspect:")
    #         print(f"{'Aspect':<40} {'Token Reads':>15}")
    #         print("-" * 60)

    #         for _, row in patterns['token_reads'].nlargest(15, 'token_read_count').iterrows():
    #             print(f"{row['aspect']:<40} {int(row['token_read_count']):>15,}")

    #     if not patterns['copy_nodes'].empty:
    #         print("\nCopy Node Statistics by Aspect:")
    #         print(f"{'Aspect':<40} {'Copy Nodes':>15}")
    #         print("-" * 60)

    #         for _, row in patterns['copy_nodes'].nlargest(15, 'copy_node_count').iterrows():
    #             print(f"{row['aspect']:<40} {int(row['copy_node_count']):>15,}")

    #     if not patterns['flushes'].empty:
    #         print("\nFlush Statistics by Aspect:")
    #         print(f"{'Aspect':<40} {'Flushes':>15}")
    #         print("-" * 60)

    #         for _, row in patterns['flushes'].nlargest(15, 'flush_count').iterrows():
    #             print(f"{row['aspect']:<40} {int(row['flush_count']):>15,}")

    # Section 6: Temporal Patterns
    # if metrics['temporal']:
    #     print("\n" + "="*80)
    #     print("SECTION 6: TEMPORAL PATTERNS")
    #     print("="*80)

    #     temporal = metrics['temporal']
    #     bin_size_ms = temporal['bin_size'] / 1e6

    #     if not temporal['events_per_bin'].empty:
    #         print(f"\nActivity Over Time (bin size: {bin_size_ms:.1f}ms):")
    #         events_per_bin = temporal['events_per_bin']
    #         print(f"  Total bins:        {len(events_per_bin):>10,}")
    #         print(f"  Mean events/bin:   {events_per_bin['event_count'].mean():>10,.0f}")
    #         print(f"  Max events/bin:    {events_per_bin['event_count'].max():>10,}")
    #         print(f"  Min events/bin:    {events_per_bin['event_count'].min():>10,}")

    #     if not temporal['cache_by_time'].empty:
    #         print("\nCache Hit Rate Over Time:")
    #         cache_trend = temporal['cache_by_time']
    #         if 'hit_rate' in cache_trend.columns and not cache_trend['hit_rate'].empty:
    #             print(f"  Initial hit rate:  {cache_trend['hit_rate'].iloc[0]:>9.2f}%")
    #             print(f"  Final hit rate:    {cache_trend['hit_rate'].iloc[-1]:>9.2f}%")
    #             print(f"  Mean hit rate:     {cache_trend['hit_rate'].mean():>9.2f}%")

    # # Section 7: Outliers and Recommendations
    # if metrics['outliers_analysis']:
    #     print("\n" + "="*80)
    #     print("SECTION 7: OUTLIERS AND RECOMMENDATIONS")
    #     print("="*80)

    #     outliers_analysis = metrics['outliers_analysis']

    #     if 'outliers' in outliers_analysis and 'performance' in outliers_analysis['outliers']:
    #         perf_outliers = outliers_analysis['outliers']['performance']
    #         if not perf_outliers.empty:
    #             print("\nPerformance Outliers (>3σ from mean):")
    #             print(f"{'Aspect':<30} {'Attribute':<45} {'Count':>10} {'Mean (μs)':>14} {'Max (μs)':>14}")
    #             print("-" * 125)

    #             for _, row in perf_outliers.head(20).iterrows():
    #                 aspect = row['aspect'][:30]
    #                 attribute = row['attribute'][:45]
    #                 count = int(row['duration_count'])
    #                 mean = row['duration_mean'] / 1e3
    #                 max_val = row['duration_max'] / 1e3
    #                 print(f"{aspect:<30} {attribute:<45} {count:>10,} {mean:>14.2f} {max_val:>14.2f}")

    #     if 'recommendations' in outliers_analysis and not isinstance(outliers_analysis['recommendations'], list):
    #         recs = outliers_analysis['recommendations']
    #         if not recs.empty:
    #             print("\nTop 20 Optimization Opportunities (by anomaly score):")
    #             print(f"{'Aspect':<30} {'Attribute':<45} {'Anomaly':>12} {'Time (ms)':>14} {'Hit Rate':>10}")
    #             print("-" * 125)

    #             for _, row in recs.head(20).iterrows():
    #                 aspect = str(row['aspect'])[:30]
    #                 attribute = str(row['attribute'])[:45]
    #                 print(f"{aspect:<30} {attribute:<45} {row['anomaly_score']:>12.3f} "
    #                       f"{row['total_time']/1e6:>14.2f} {row['hit_rate']:>9.2f}%")

    #             print("\nRecommendations:")
    #             print("  - Focus on attributes with high anomaly scores")
    #             print("  - Attributes with high total time and low hit rates are prime optimization targets")
    #             print("  - Consider improving caching strategies for frequently computed attributes")
    #             print("  - Investigate circular evaluations with high iteration counts")

    # print("\n" + "="*80)
    # print(" "*25 + "END OF ANALYSIS")
    # print("="*80 + "\n")


def main():
    """Main entry point for the trace analysis script."""
    parser = argparse.ArgumentParser(
        description='Compute comprehensive metrics from attribute grammar trace data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
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
    )
    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to the CSV trace log file',
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_file)

    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        return 1

    print(f"Analyzing trace file: {csv_path}")

    # Read the data
    df = read_csv_to_dataframe(csv_path)

    if df.empty:
        print("No events found in the log file.")
        return 1

    # Compute all metrics
    metrics = process_nesting_data(df)

    # Present results
    present_results(metrics, csv_path)

    return 0





if __name__ == "__main__":
    main()


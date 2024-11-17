import json
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
import os
from datetime import datetime

import numpy as np

class BenchmarkVisualizer:
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'total_issues': 0,
            'build_failures': 0,
            'validation_failures': 0,
            'successful_patches': 0,
            'total_attempts': 0,
            'non_applicabale_diffs': 0,
            'model_name': '',
            'timestamp': None,
            'prompt_tokens': 0,
            'response_tokens': 0,
            'warnings_distribution': {},
            'original_warnings_distribution': {},
            'elapsed_time': 0.0
        })

    def update_metrics(self, model_name, stats_data):
        """Update metrics for a specific model run"""
        self.metrics[model_name].update({
            'total_issues': stats_data.get('total_issues', 0),
            'build_failures': stats_data.get('build_failures', 0),
            'validation_failures': stats_data.get('validation_failures', 0),
            'non_applicabale_diffs': stats_data.get('non_applicabale_diffs', 0),
            'successful_patches': stats_data.get('successful_patches', 0),
            'total_attempts': stats_data.get('total_attempts', 0),
            'prompt_tokens': stats_data.get('prompt_tokens', 0),
            'response_tokens': stats_data.get('response_tokens', 0),
            'model_name': model_name,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'warnings_distribution': stats_data.get('warnings_dict', {}),
            'original_warnings_distribution': stats_data.get('original_warnings_dict', {}),
            'elapsed_time': stats_data.get('elapsed_time', 0.0)
        })

    # def generate_comparison_charts(self, output_dir):
    #     """Generate comparative visualization charts"""
    #     if not self.metrics:
    #         return



    #     models = list(self.metrics.keys())
    #     metrics_to_plot = ['successful_patches', 'compilation_errors', 'sast_failures', 'non_applicabale_diffs']


    #     plt.figure(figsize=(12, 6))
    #     x = range(len(models))
    #     width = 0.25

    #     for i, metric in enumerate(metrics_to_plot):
    #         values = [self.metrics[model][metric] for model in models]
    #         plt.bar([xi + width*i for xi in x], values, width, 
    #                label=metric.replace('_', ' ').title())

    #     plt.xlabel('Models')
    #     plt.ylabel('Count')
    #     plt.title('Patch Generation Performance')
    #     plt.xticks([xi + width for xi in x], models)
    #     plt.legend()
    #     plt.savefig(os.path.join(output_dir, 'patch_generation_performence.png'))
    #     plt.close()


    #     for model in models:
    #         plt.figure(figsize=(8, 8))

    #         total = sum(self.metrics[model][metric] for metric in metrics_to_plot)
    #         sizes = [self.metrics[model][metric] for metric in metrics_to_plot]

    #         if total > 0:
    #             sizes = [size/total * 100 for size in sizes]

    #         colors = ['#4CAF50', '#FF6347', '#FFA500', '#808080']
    #         plt.pie(sizes, labels=metrics_to_plot, colors=colors,
    #                autopct='%1.1f%%', startangle=140)
    #         plt.title(f'{model} Performance Distribution')

    #         for i, metric in enumerate(metrics_to_plot):
    #             count = self.metrics[model][metric]
    #             plt.text(0, -1.2 - i*0.1, f"{metric.replace('_', ' ').title()}: {count}", 
    #                     ha='center', fontsize=10)

    #         plt.savefig(os.path.join(output_dir, f'{model}_distribution.png'))
    #         plt.close()



    #         plt.figure(figsize=(12, 6))
    #         x = range(len(models))
    #         width = 0.25

    #         for i, metric in enumerate(['prompt_tokens', 'response_tokens']):
    #             values = [self.metrics[model][metric] for model in models]
    #             plt.bar([xi + width * i for xi in x], values, width, 
    #                     label=metric.replace('_', ' ').title())

    #         plt.xlabel('Models')
    #         plt.ylabel('Token Count')
    #         plt.title('Token Counts Comparison')
    #         plt.xticks([xi + width / 2 for xi in x], models)
    #         plt.legend()
    #         plt.savefig(os.path.join(output_dir, 'token_counts_comparison.png'))
    #         plt.close()


    #         warnings_dist = self.metrics[model].get('warnings_distribution', {})
    #         if warnings_dist:
    #             plt.figure(figsize=(15, 8))
    #             warnings_names = list(warnings_dist.keys())
    #             warnings_counts = list(warnings_dist.values())
                

    #             y_pos = range(len(warnings_names))
    #             plt.barh(y_pos, warnings_counts, align='center')
    #             plt.yticks(y_pos, warnings_names)
                
    #             plt.xlabel('Count')
    #             plt.title(f'{model} Remaining Warnings Distribution')
                
    #             plt.tight_layout()
    #             plt.savefig(os.path.join(output_dir, f'{model}_warnings_distribution.png'))
    #             plt.close()
            



    #     for model, data in self.metrics.items():
    #         original_warnings = data.get('original_warnings_distribution', {})
    #         remaining_warnings = data.get('warnings_distribution', {})

    #         all_warning_types = set(original_warnings.keys()).union(remaining_warnings.keys())
    #         original_counts = [original_warnings.get(w, 0) for w in all_warning_types]
    #         remaining_counts = [remaining_warnings.get(w, 0) for w in all_warning_types]


    #         plt.figure(figsize=(12, 8))
    #         x = range(len(all_warning_types))
    #         bar_width = 0.35

    #         plt.bar(x, original_counts, width=bar_width, color='skyblue', label='Original')
    #         plt.bar([i + bar_width for i in x], remaining_counts, width=bar_width, color='salmon', label='After Patch')

    #         plt.xlabel('Warning Type')
    #         plt.ylabel('Count')
    #         plt.title(f'{model} Warning Counts (Before vs After Patch)')
    #         plt.xticks([i + bar_width / 2 for i in x], all_warning_types, rotation=45, ha='right')
    #         plt.legend()

    #         plt.tight_layout()
    #         plt.savefig(os.path.join(output_dir, f'{model}_warnings_comparison.png'))
    #         plt.close()

    def generate_comparison_charts(self, output_dir):
        """Generate comparative visualization charts for each model."""
        if not self.metrics:
            print("No metrics data available to generate charts.")
            return

        # Ensure the output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Loop through each model in the metrics
        for model_name, model_data in self.metrics.items():
            # Extract warning distributions
            original_warnings_distribution = model_data.get("original_warnings_distribution", {})
            after_patch_warnings_distribution = model_data.get("warnings_distribution", {})

            # Sort warning types by original counts in descending order
            sorted_keys = sorted(
                original_warnings_distribution,
                key=original_warnings_distribution.get,
                reverse=True
            )
            original_counts = [original_warnings_distribution[key] for key in sorted_keys]
            after_patch_counts = [after_patch_warnings_distribution.get(key, 0) for key in sorted_keys]

            # Create the figure and subplots
            fig = plt.figure(figsize=(16, 10))
            gs = GridSpec(2, 2, figure=fig, height_ratios=[4, 1])

            # Subplot 1: Warning Counts Before vs After Patch
            ax1 = fig.add_subplot(gs[0, 0])
            index = np.arange(len(sorted_keys))
            bar_width = 0.35

            bars1 = ax1.bar(index, original_counts, bar_width, label='Original')
            bars2 = ax1.bar(index + bar_width, after_patch_counts, bar_width, label='After Patch')

            ax1.set_xlabel('Warning Type')
            ax1.set_ylabel('Count')
            ax1.set_title('Warning Counts (Before vs After Patch)')
            ax1.set_xticks(index + bar_width / 2)
            ax1.set_xticklabels(sorted_keys, rotation=45, ha="right")
            ax1.legend()

            # Subplot 2: Performance Distribution Pie Chart
            ax2 = fig.add_subplot(gs[0, 1])
            labels = ['successful_patches', 'compilation_errors', 'validation_failures', 'non_applicabale_diffs']
            sizes = [
                model_data.get('successful_patches', 0),
                model_data.get('compilation_errors', 0),
                model_data.get('validation_failures', 0),
                model_data.get('non_applicabale_diffs', 0)
            ]
            colors = ['#66c2a5', '#fc8d62', '#ffd92f', '#8da0cb']
            explode = [0, 0.1, 0.1, 0.1]

            ax2.pie(
                sizes,
                labels=labels,
                autopct='%1.1f%%',
                startangle=150,
                colors=colors,
                explode=explode,
                wedgeprops=dict(edgecolor='black'),
                pctdistance=0.70,
                labeldistance=1.4
            )
            ax2.set_title(f"{model_data.get('model_name', model_name)} Performance Distribution", pad=5)

            legend_labels = [
                f"{label.replace('_', ' ').title()}: {size}"
                for label, size in zip(labels, sizes)
            ]
            ax2.legend(legend_labels, loc="center left", bbox_to_anchor=(1, 0.5))

            # Subplot 3: Token Counts Comparison
            ax3 = fig.add_subplot(gs[1, :])
            prompt_tokens = model_data.get('prompt_tokens', 0)
            response_tokens = model_data.get('response_tokens', 0)
            token_counts = [prompt_tokens, response_tokens]

            bar_labels = ['Prompt Tokens', 'Response Tokens']
            bar_colors = ['#1f77b4', '#ff7f0e']
            bars = ax3.bar(bar_labels, token_counts, color=bar_colors, width=0.4)

            # Annotate bars with token counts
            for bar, label in zip(bars, token_counts):
                height = bar.get_height()
                ax3.text(
                    bar.get_x() + bar.get_width() / 2,
                    height / 2,
                    f'{label}',
                    ha='center',
                    va='center',
                    color='white',
                    fontsize=12
                )

            ax3.set_xlabel('Token Type')
            ax3.set_ylabel('Token Count')
            ax3.set_title('Token Counts Comparison')
            ax3.legend(bar_labels)

            plt.tight_layout()

            # Save the figure to the output directory
            output_file = os.path.join(output_dir, f"{model_name}_charts.png")
            plt.savefig(output_file)
            plt.close()

            print(f"Charts for model '{model_name}' saved to '{output_file}'.")

    def save_metrics(self, output_path):
        """Save metrics to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(self.metrics, f, indent=4)

    def load_metrics(self, input_path):
        """Load metrics from JSON file"""
        if os.path.exists(input_path):
            with open(input_path, 'r') as f:
                self.metrics = json.load(f)
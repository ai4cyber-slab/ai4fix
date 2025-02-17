import json
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
from collections import defaultdict
import os
from datetime import datetime
from utils.logger import logger

import numpy as np

class BenchmarkVisualizer:
    def __init__(self, num_of_rounds):
        self.metrics = defaultdict(lambda: {
            'total_issues': 0,
            'build_failures': 0,
            'validation_failures': 0,
            'successful_patches': 0,
            'total_attempts': 0,
            'non_applicabale_diffs': 0,
            'introduced_new_issue': 0,
            'model_name': '',
            'timestamp': None,
            'prompt_tokens': 0,
            'response_tokens': 0,
            'warnings_distribution': {},
            'original_warnings_distribution': {},
            'elapsed_time': 0.0
        })
        self.num_of_rounds = num_of_rounds

    def update_metrics(self, model_name, stats_data):
        """Update metrics for a specific model run"""
        self.metrics[model_name].update({
            'total_issues': stats_data.get('total_issues', 0),
            'build_failures': stats_data.get('build_failures', 0),
            'validation_failures': stats_data.get('validation_failures', 0),
            'non_applicabale_diffs': stats_data.get('non_applicabale_diffs', 0),
            'introduced_new_issue': stats_data.get('introduced_new_issue', 0),
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

    def generate_comparison_charts(self, output_dir):
        """Generate comparative visualization charts for each model."""
        if not self.metrics:
            logger.warning("No metrics data available to generate charts.")
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for model_name, model_data in self.metrics.items():
            original_warnings_distribution = model_data.get("original_warnings_distribution", {})
            after_patch_warnings_distribution = model_data.get("warnings_distribution", {})

            sorted_keys = sorted(
                original_warnings_distribution,
                key=original_warnings_distribution.get,
                reverse=True
            )
            original_counts = [original_warnings_distribution[key] for key in sorted_keys]
            after_patch_counts = [after_patch_warnings_distribution.get(key, 0) for key in sorted_keys]

            fig = plt.figure(figsize=(16, 10))
            gs = GridSpec(2, 2, figure=fig, height_ratios=[4, 1])

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

            for i, count in enumerate(original_counts):
                ax1.text(i, count + 0.2, str(count), ha='center', fontsize=9)
            for i, count in enumerate(after_patch_counts):
                ax1.text(i + bar_width, count + 0.2, str(count), ha='center', fontsize=9)

            ax2 = fig.add_subplot(gs[0, 1])
            labels = [
                'Successful Patches',
                'Build Failures',
                'Validation Failures',
                'Non-Applicable Diffs'
            ]
            sizes = [
                model_data.get('successful_patches', 0),
                model_data.get('build_failures', 0),
                model_data.get('introduced_new_issue', 0),
                model_data.get('non_applicabale_diffs', 0)
            ]
            colors = ['#66c2a5', '#fc8d62', '#ffd92f', '#8da0cb']
            explode = [0, 0.1, 0.1, 0.1]

            sizes = [
                max(0, np.nan_to_num(model_data.get('successful_patches', 0), nan=0.0, posinf=0.0, neginf=0.0)),
                max(0, np.nan_to_num(model_data.get('build_failures', 0), nan=0.0, posinf=0.0, neginf=0.0)),
                max(0, np.nan_to_num(model_data.get('introduced_new_issue', 0), nan=0.0, posinf=0.0, neginf=0.0)),
                max(0, np.nan_to_num(model_data.get('non_applicabale_diffs', 0), nan=0.0, posinf=0.0, neginf=0.0))
            ]

            if sum(sizes) > 0:
                wedges, texts, autotexts = ax2.pie(
                    sizes,
                    autopct='%1.1f%%',
                    startangle=150,
                    colors=colors,
                    explode=explode,
                    wedgeprops=dict(edgecolor='black'),
                    pctdistance=0.70,
                    labeldistance=None
                )
                ax2.set_title(f"{model_data.get('model_name', model_name)} Performance Distribution", pad=5)
                legend_labels = [
                    f"{label}: {size}" for label, size in zip(labels, sizes)
                ]
                ax2.legend(legend_labels, loc="center left", bbox_to_anchor=(1, 0.5))
                ax2.set_title(f"{model_data.get('model_name', model_name)} Performance Distribution", pad=5)
                legend_labels = [
                f"{label}: {size}" for label, size in zip(labels, sizes)
                ]
                ax2.legend(legend_labels, loc="center left", bbox_to_anchor=(1, 0.5))
            else:
                logger.warning(f"Skipping pie chart for model '{model_name}' due to zero or invalid data.")

            # Subplot 3: Token Counts Comparison
            ax3 = fig.add_subplot(gs[1, :])
            prompt_tokens = model_data.get('prompt_tokens', 0)
            response_tokens = model_data.get('response_tokens', 0)
            token_counts = [prompt_tokens, response_tokens]

            bar_labels = ['Prompt Tokens', 'Response Tokens']
            bar_colors = ['#1f77b4', '#ff7f0e']
            bars = ax3.bar(bar_labels, token_counts, color=bar_colors, width=0.4)

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
            ax3.legend(bars, bar_labels, loc="upper right")

            plt.tight_layout()

            output_file = os.path.join(output_dir, f"{model_name}_charts_round_{self.num_of_rounds}.png")
            plt.savefig(output_file)
            plt.close()

            logger.info(f"Charts for model '{model_name}' saved to '{output_file}'.")

    def save_metrics(self, output_path):
        """Save metrics to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(self.metrics, f, indent=4)

    def load_metrics(self, input_path):
        """Load metrics from JSON file"""
        if os.path.exists(input_path):
            with open(input_path, 'r') as f:
                self.metrics = json.load(f)
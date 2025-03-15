"""
Report generator for more detailed analysis and visualization
"""

import os
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

from loguru import logger
from models.application_page import ApplicationPageCollection


class ReportGenerator:
    """Generate detailed reports and visualizations from crawler results."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_full_report(
        self,
        application_pages: List[Dict],
        crawl_stats: Optional[Dict] = None,
        api_metrics: Optional[Dict] = None,
    ) -> str:
        """Generate a comprehensive HTML report with visualizations."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_dir, f"full_report_{timestamp}.html")

        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(application_pages)

        # Generate visualizations
        self._generate_visualizations(df, timestamp)

        # Build HTML report
        with open(report_file, "w") as f:
            f.write("<html><head>")
            f.write("<style>")
            f.write("body { font-family: Arial, sans-serif; margin: 20px; }")
            f.write("h1, h2, h3 { color: #333366; }")
            f.write("table { border-collapse: collapse; width: 100%; }")
            f.write(
                "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }"
            )
            f.write("tr:nth-child(even) { background-color: #f2f2f2; }")
            f.write("th { background-color: #4CAF50; color: white; }")
            f.write(".stats { display: flex; flex-wrap: wrap; }")
            f.write(
                ".stat-box { padding: 15px; margin: 10px; background-color: #f8f8f8; border-radius: 5px; flex: 1; }"
            )
            f.write("</style>")
            f.write("</head><body>")

            # Title and overview
            f.write(f"<h1>University Application Crawler Report</h1>")
            f.write(
                f"<p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
            )

            # Key statistics
            f.write("<h2>Key Statistics</h2>")
            f.write("<div class='stats'>")

            # Application pages stats
            actual_pages = len(
                [p for p in application_pages if p.get("is_actual_application", False)]
            )
            f.write(f"<div class='stat-box'><h3>Found Pages</h3>")
            f.write(f"<p>Total pages analyzed: {len(application_pages)}</p>")
            f.write(f"<p>Actual application pages: {actual_pages}</p>")
            f.write(
                f"<p>Success rate: {actual_pages/len(application_pages)*100:.1f}%</p>"
            )
            f.write("</div>")

            # Crawl stats if available
            if crawl_stats:
                f.write(f"<div class='stat-box'><h3>Crawl Performance</h3>")
                f.write(
                    f"<p>URLs visited: {crawl_stats.get('total_urls_visited', 0)}</p>"
                )
                f.write(
                    f"<p>Domains explored: {len(crawl_stats.get('domain_visit_counts', {}))}</p>"
                )
                f.write(
                    f"<p>Admission domains found: {len(crawl_stats.get('admission_related_domains', []))}</p>"
                )
                f.write("</div>")

            # API metrics if available
            if api_metrics:
                f.write(f"<div class='stat-box'><h3>AI Evaluation</h3>")
                f.write(
                    f"<p>Pages evaluated: {api_metrics.get('pages_evaluated', 0)}</p>"
                )
                f.write(f"<p>Total tokens: {api_metrics.get('total_tokens', 0)}</p>")
                f.write(
                    f"<p>Cost: ${api_metrics.get('estimated_cost_usd', 0.0):.4f}</p>"
                )
                f.write("</div>")

            f.write("</div>")  # Close stats div

            # Visualizations
            f.write("<h2>Visualizations</h2>")
            f.write("<div style='display: flex; flex-wrap: wrap;'>")
            f.write(
                f"<div style='flex: 1;'><img src='university_distribution_{timestamp}.png' width='100%'></div>"
            )
            f.write(
                f"<div style='flex: 1;'><img src='application_types_{timestamp}.png' width='100%'></div>"
            )
            f.write("</div>")

            # University breakdown
            f.write("<h2>Results by University</h2>")

            # Group by university
            by_university = {}
            for app in application_pages:
                univ = app.get("university", "Unknown")
                if univ not in by_university:
                    by_university[univ] = []
                by_university[univ].append(app)

            # Create a table of universities and their application pages
            for univ, apps in by_university.items():
                actual_apps = [a for a in apps if a.get("is_actual_application", False)]

                f.write(f"<h3>{univ}</h3>")
                f.write(
                    f"<p>Found {len(apps)} potential pages, {len(actual_apps)} actual application pages</p>"
                )

                # Table of actual application pages
                if actual_apps:
                    f.write("<h4>Actual Application Pages</h4>")
                    f.write("<table>")
                    f.write("<tr><th>Title</th><th>URL</th><th>AI Evaluation</th></tr>")

                    for app in actual_apps:
                        f.write("<tr>")
                        f.write(f"<td>{app.get('title', 'No title')}</td>")
                        f.write(
                            f"<td><a href='{app.get('url', '')}' target='_blank'>{app.get('url', '')}</a></td>"
                        )
                        f.write(f"<td>{app.get('ai_evaluation', 'No evaluation')}</td>")
                        f.write("</tr>")

                    f.write("</table>")

                # Table of information pages
                info_apps = [
                    a for a in apps if not a.get("is_actual_application", False)
                ]
                if info_apps:
                    f.write("<h4>Information Pages</h4>")
                    f.write("<table>")
                    f.write("<tr><th>Title</th><th>URL</th><th>AI Evaluation</th></tr>")

                    for app in info_apps:
                        f.write("<tr>")
                        f.write(f"<td>{app.get('title', 'No title')}</td>")
                        f.write(
                            f"<td><a href='{app.get('url', '')}' target='_blank'>{app.get('url', '')}</a></td>"
                        )
                        f.write(f"<td>{app.get('ai_evaluation', 'No evaluation')}</td>")
                        f.write("</tr>")

                    f.write("</table>")

            # Close HTML
            f.write("</body></html>")

        logger.success(f"Generated full HTML report at {report_file}")
        return report_file

    def _generate_visualizations(self, df, timestamp):
        """Generate visualization images for the report."""
        try:
            # University distribution chart
            plt.figure(figsize=(10, 6))
            university_counts = df["university"].value_counts()
            university_counts.plot(kind="bar", color="skyblue")
            plt.title("Pages Found by University")
            plt.xlabel("University")
            plt.ylabel("Number of Pages")
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    self.output_dir, f"university_distribution_{timestamp}.png"
                )
            )
            plt.close()

            # Application types pie chart
            plt.figure(figsize=(8, 8))
            app_types = df["is_actual_application"].value_counts()
            labels = ["Application Pages", "Information Pages"]
            plt.pie(
                app_types,
                labels=labels,
                autopct="%1.1f%%",
                colors=["#4CAF50", "#FFC107"],
            )
            plt.title("Types of Pages Found")
            plt.tight_layout()
            plt.savefig(
                os.path.join(self.output_dir, f"application_types_{timestamp}.png")
            )
            plt.close()

        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")

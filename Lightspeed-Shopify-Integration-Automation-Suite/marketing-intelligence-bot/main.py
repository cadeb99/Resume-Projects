"""
Entry point. Run weekly via cron / Cloud Scheduler once deployed; runs
directly for manual testing right now.
"""
import sys
import config
import aggregator
import reports.report_generator as report_generator
import reports.gmail_sender as gmail_sender


def main():
    mode = "DEMO" if config.DEMO_MODE else "LIVE"
    print(f"Running {config.STORE_NAME} marketing intelligence report — mode: {mode}")

    context = aggregator.run_pipeline()

    print(f"\nSeason context: {context['season']}")
    print(f"Top {len(context['top_products'])} products to advertise:")
    for p in context["top_products"]:
        print(f"  - [{p['channel']}] {p['name']} ({p['store']}) — score {p['composite_score']} — {'; '.join(p['reasons'])}")

    if context["listing_flags"]:
        print(f"\nOnline listing flags ({len(context['listing_flags'])}):")
        for p in context["listing_flags"]:
            print(f"  - {p['name']}: {p['listing_flag']}")

    html = report_generator.build_html_report(context)
    output = gmail_sender.send_report(html)
    print(f"\nDone. Report output: {output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)

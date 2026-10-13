"""Command line entry point: `news-insights serve | stories | search | alerts`."""

from __future__ import annotations

import argparse
import json
import sys

from news_insights.api import default_pipeline


def _print(rows: list) -> None:
    json.dump([r.model_dump(mode="json") for r in rows], sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="news-insights", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="Run the API and web page")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    stories = commands.add_parser("stories", help="List the latest stories")
    stories.add_argument("--ticker")
    stories.add_argument("--limit", type=int, default=10)

    search = commands.add_parser("search", help="Search stories")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)

    alerts = commands.add_parser("alerts", help="Strong positive or negative stories")
    alerts.add_argument("--watchlist", help="Comma-separated tickers")

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("news_insights.api:create_app", factory=True, host=args.host, port=args.port)
        return

    store = default_pipeline().store
    if args.command == "stories":
        _print(store.list_stories(ticker=args.ticker, limit=args.limit))
    elif args.command == "search":
        for hit in store.search(args.query, limit=args.limit):
            print(f"{hit.score:.2f}  {hit.story.headline}  [{', '.join(hit.matched)}]")
    elif args.command == "alerts":
        watch = set(args.watchlist.split(",")) if args.watchlist else None
        for alert in store.alerts(watch):
            print(
                f"{alert.ticker:5} {alert.direction.value:8} conf={alert.confidence:.1f} "
                f"sentiment={alert.sentiment_score:+.2f}  {alert.headline}"
            )


if __name__ == "__main__":
    main()

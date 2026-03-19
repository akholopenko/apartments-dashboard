import argparse
from datetime import date

from core import get_dashboard_data


def render_table(rows):
    headers = [
        "Date",
        "Check-ins",
        "Check-outs",
        "Potential check-outs",
        "Check-in apartments",
        "Check-out apartments",
        "Potential apartments",
    ]

    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["date"],
                row["checkins_count"],
                row["checkouts_count"],
                row["potential_count"],
                ", ".join(row["checkins_apartments"]) or "-",
                ", ".join(row["checkouts_apartments"]) or "-",
                ", ".join(row["potential_apartments"]) or "-",
            ]
        )

    all_rows = [headers] + table_rows
    widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    def fmt_row(row):
        return " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    line = "-+-".join("-" * w for w in widths)
    print(fmt_row(headers))
    print(line)
    for row in table_rows:
        print(fmt_row(row))


def main():
    parser = argparse.ArgumentParser(
        description="Daily apartment operations dashboard: check-ins, check-outs and potential check-outs."
    )
    parser.add_argument("--days", type=int, default=21, help="Number of days to show")
    parser.add_argument(
        "--start-date",
        default=date.today().isoformat(),
        help="Start date in YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()

    data = get_dashboard_data(days=args.days, start_date=args.start_date)

    print()
    render_table(data["rows"])
    print()

    if data["warnings"]:
        print("Source warnings:")
        for item in data["warnings"]:
            print(f"- {item['apartment']} | {item['url']}")
            print(f"  {item['error']}")


if __name__ == "__main__":
    main()

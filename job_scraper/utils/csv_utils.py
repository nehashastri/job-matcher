import csv


def write_dicts_to_csv(filepath, fieldnames, rows, logger):
    logger.info(f"Writing {len(rows)} rows to CSV: {filepath}")
    try:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        logger.info(f"Successfully wrote CSV: {filepath}")
        return True
    except Exception as exc:
        logger.error(f"Error writing {filepath}: {exc}")
        return False

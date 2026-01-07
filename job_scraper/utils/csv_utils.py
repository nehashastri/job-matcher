import csv


def write_dicts_to_csv(filepath, fieldnames, rows, logger):
    """
    Write a list of dictionaries to a CSV file with specified fieldnames.

    Args:
        filepath: Path to the CSV file to write.
        fieldnames: List of column names for the CSV header.
        rows: List of dictionaries, each representing a row of data.
        logger: Logger object for logging progress and errors.

    Returns:
        True if writing succeeds, False otherwise.
    """
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

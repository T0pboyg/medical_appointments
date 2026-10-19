import time

import psycopg

from cleanup import cleanup_expired_data


def run_cleanup_worker():
    while True:
        try:
            result = cleanup_expired_data()
            print("Cleanup completed:", result, flush=True)
        except psycopg.Error:
            print(
                "Cleanup failed: database operation unavailable. "
                "Retrying in 5 minutes.",
                flush=True,
            )

        time.sleep(300)


if __name__ == "__main__":
    run_cleanup_worker()
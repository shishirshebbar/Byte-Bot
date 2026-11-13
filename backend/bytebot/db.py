from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def make_pool(url):
    return ConnectionPool(url, min_size=0, max_size=8, timeout=3,
                          kwargs={"row_factory": dict_row, "connect_timeout": 3}, open=False)

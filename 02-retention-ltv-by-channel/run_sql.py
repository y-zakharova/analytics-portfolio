"""Run every query in queries.sql against the CSVs with DuckDB and print the results.
pip install duckdb pandas, then: python run_sql.py"""
import re
import duckdb

con = duckdb.connect()
con.execute("CREATE VIEW users AS SELECT * FROM 'data/users.csv.gz'")
con.execute("CREATE VIEW transactions AS SELECT * FROM 'data/transactions.csv'")
con.execute("CREATE VIEW marketing_spend AS SELECT * FROM 'data/marketing_spend.csv'")
sql = open("queries.sql").read()
titles = re.findall(r"^-- (\d+\. .+)$", sql, flags=re.M)
queries = [q.strip() for q in re.sub(r"--[^\n]*", "", sql).split(";") if q.strip()]
for title, q in zip(titles, queries):
    print(f"\n=== {title} ===")
    print(con.execute(q).df().to_string(index=False))

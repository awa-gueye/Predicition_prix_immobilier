import psycopg2

conn = psycopg2.connect(
    database="scrapy_immo",
    user="Cardan",
    password="Fatimata05?",
    host="localhost",
    port=5432
)
cur = conn.cursor()
cur.execute("SELECT NOW();")
print(cur.fetchone())
conn.close()

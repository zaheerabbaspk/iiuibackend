import psycopg2
from psycopg2.extras import RealDictCursor

def check_db():
    try:
        conn = psycopg2.connect(
            dbname="university_voting",
            user="postgres",
            password="blove1234@",
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchall()
        print("Tables in DB:", tables)
        
        cur.execute("SELECT * FROM voting_tokens LIMIT 1")
        print("voting_tokens table is accessible.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_db()

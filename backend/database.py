import psycopg2
from psycopg2.extras import RealDictCursor
import time

# Database Configuration
DB_NAME = "university_voting"
DB_USER = "postgres"
DB_PASSWORD = "blove1234@"
DB_HOST = "localhost"
DB_PORT = "5432"

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        return None

def init_db():
    """Initializes the database tables safely without dropping data on every restart."""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to the database.")
        return

    try:
        cur = conn.cursor()
        
        # 1. Elections Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS elections (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'upcoming',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Users Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                image_url TEXT,
                has_voted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Candidates Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                position TEXT NOT NULL,
                party TEXT,
                election_id TEXT,
                image_url TEXT,
                vote_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Votes Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_vote UNIQUE (user_id)
            );
        """)

        # 5. Voting Tokens Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS voting_tokens (
                id SERIAL PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                batch_id TEXT,
                election_id TEXT, 
                is_used BOOLEAN DEFAULT FALSE,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Junction table for tokens and multiple elections
        cur.execute("""
            CREATE TABLE IF NOT EXISTS token_elections (
                id SERIAL PRIMARY KEY,
                token_id INTEGER REFERENCES voting_tokens(id) ON DELETE CASCADE,
                election_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 7. Insert Initial Data ONLY if candidates table is empty
        cur.execute("SELECT COUNT(*) FROM candidates")
        if cur.fetchone()['count'] == 0:
            print("Inserting initial candidate data...")
            cur.execute("""
                INSERT INTO candidates (name, position, party, election_id, image_url) VALUES
                ('Candidate A', 'President', 'Party X', 'ELEC-001', 'https://yourdomain.com/uploads/candidate_a.jpg'),
                ('Candidate B', 'Vice President', 'Party Y', 'ELEC-001', 'https://yourdomain.com/uploads/candidate_b.jpg'),
                ('Candidate C', 'General Secretary', 'Independent', 'ELEC-001', 'https://yourdomain.com/uploads/candidate_c.jpg');
            """)

        conn.commit()
        cur.close()
        print("Database checked/initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
    finally:
        conn.close()

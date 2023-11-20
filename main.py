import psycopg2
from sshtunnel import SSHTunnelForwarder
import os
from dotenv import load_dotenv
import commandEntry as ce

load_dotenv()

username = os.getenv("DB_USERNAME")
password = os.getenv("DB_PASSWORD")
dbName = "p320_13"

try:
    with SSHTunnelForwarder(('starbug.cs.rit.edu', 22),
                            ssh_username=username,
                            ssh_password=password,
                            remote_bind_address=('localhost', 5432)) as server:
        server.start()
        print("SSH tunnel established")
        params = {
            'database': dbName,
            'user': username,
            'password': password,
            'host': 'localhost',
            'port': server.local_bind_port
        }

        conn = psycopg2.connect(**params)
        curs = conn.cursor()

        print("Database connection established")

        ce.command_branch(curs, conn)
        # curs.execute("SELECT * FROM p320_13.\"user\"")
        # rows = curs.fetchall()
        # print(rows)
        
        conn.commit()
        conn.close()
except Exception as e:
    print(e)
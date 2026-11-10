import psycopg

conn = psycopg.connect("postgresql://postgres@127.0.0.1:5432/postgres", autocommit=True)
roles = [row[0] for row in conn.execute("SELECT usename FROM pg_user")]
if "bgm" not in roles:
    conn.execute("CREATE USER bgm WITH PASSWORD 'bgm_dev_password' SUPERUSER")
    print("created role bgm")
else:
    print("role bgm already exists")

dbs = [row[0] for row in conn.execute("SELECT datname FROM pg_database")]
if "bgm_travels" not in dbs:
    conn.execute("CREATE DATABASE bgm_travels OWNER bgm")
    print("created database bgm_travels")
else:
    print("database bgm_travels already exists")
print("DB_READY")

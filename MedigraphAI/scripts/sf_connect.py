import os
from dotenv import load_dotenv
import snowflake.connector as sf

load_dotenv(".env", override=True)

totp = input("Enter current Snowflake TOTP (6 digits): ").strip()

conn = sf.connect(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    host=os.getenv("SNOWFLAKE_HOST"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA"),
    authenticator="snowflake",
    passcode=totp,
)
cur = conn.cursor()
cur.execute("SELECT current_account(), current_region(), current_warehouse(), current_database(), current_schema()")
print("✅ Snowflake OK:", cur.fetchone())
cur.close(); conn.close()
0

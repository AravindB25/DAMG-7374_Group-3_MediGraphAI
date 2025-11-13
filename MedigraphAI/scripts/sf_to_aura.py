import os
from dotenv import load_dotenv
import snowflake.connector
from neo4j import GraphDatabase

# Load .env values
load_dotenv(".env", override=True)


def get_snowflake_conn(totp_code: str):
    """
    Open a single Snowflake connection using username + password + TOTP.
    This connection is reused for all ETL steps.
    """
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        passcode=totp_code,  # MFA code from Google Authenticator
    )


def get_aura_driver():
    """
    Create a Neo4j AuraDB driver from .env values.
    """
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not pwd:
        raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")

    return GraphDatabase.driver(uri, auth=(user, pwd))


def load_patients(conn, driver):
    print("Loading patients…")
    cur = conn.cursor()
    cur.execute("""
        SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, SEX, ZIP, AGE
        FROM MEDIGRAPH.PUBLIC.V_PATIENTS
    """)
    rows = cur.fetchall()
    cur.close()

    with driver.session(database="neo4j") as session:
        for pid, first, last, sex, zip_code, age in rows:
            session.run(
                """
                MERGE (p:Patient {id: $pid})
                SET p.first_name = $first,
                    p.last_name  = $last,
                    p.full_name  = $first + ' ' + $last,
                    p.sex        = $sex,
                    p.zip        = $zip,
                    p.age        = $age
                """,
                pid=pid,
                first=first,
                last=last,
                sex=sex,
                zip=str(zip_code) if zip_code is not None else None,
                age=age,
            )

    print(f"✔ Loaded {len(rows)} patients")


def load_encounters(conn, driver):
    print("Loading encounters…")
    cur = conn.cursor()
    cur.execute("""
        SELECT ENC_ID, PATIENT_ID, PROVIDER_NPI, START_TIME, END_TIME
        FROM MEDIGRAPH.PUBLIC.V_ENCOUNTERS
    """)
    rows = cur.fetchall()
    cur.close()

    with driver.session(database="neo4j") as session:
        for enc_id, pid, provider_npi, start_time, end_time in rows:
            session.run(
                """
                MERGE (p:Patient {id: $pid})
                MERGE (e:Encounter {id: $enc_id})
                SET e.start_time   = $start_time,
                    e.end_time     = $end_time,
                    e.provider_npi = $provider_npi
                MERGE (p)-[:HAS_ENCOUNTER]->(e)
                """,
                enc_id=enc_id,
                pid=pid,
                provider_npi=provider_npi,
                start_time=str(start_time) if start_time is not None else None,
                end_time=str(end_time) if end_time is not None else None,
            )

    print(f"✔ Loaded {len(rows)} encounters")


def load_conditions(conn, driver):
    print("Loading conditions…")
    cur = conn.cursor()
    cur.execute("""
        SELECT ENC_ID, PATIENT_ID, ICD_CODE, NAME
        FROM MEDIGRAPH.PUBLIC.V_CONDITIONS
    """)
    rows = cur.fetchall()
    cur.close()

    with driver.session(database="neo4j") as session:
        for enc_id, pid, icd_code, name in rows:
            session.run(
                """
                MERGE (p:Patient {id: $pid})
                MERGE (e:Encounter {id: $enc_id})
                MERGE (c:Condition {code: $code})
                SET c.name = $name
                MERGE (p)-[:HAS_CONDITION]->(c)
                MERGE (e)-[:HAS_CONDITION]->(c)
                """,
                enc_id=enc_id,
                pid=pid,
                code=icd_code,
                name=name,
            )

    print(f"✔ Loaded {len(rows)} conditions")


def load_medications(conn, driver):
    print("Loading medications…")
    cur = conn.cursor()
    cur.execute("""
        SELECT ENC_ID, PATIENT_ID, RXNORM, NAME
        FROM MEDIGRAPH.PUBLIC.V_MEDICATIONS
    """)
    rows = cur.fetchall()
    cur.close()

    with driver.session(database="neo4j") as session:
        for enc_id, pid, rxnorm, name in rows:
            session.run(
                """
                MERGE (p:Patient {id: $pid})
                MERGE (e:Encounter {id: $enc_id})
                MERGE (m:Medication {code: $code})
                SET m.name = $name
                MERGE (p)-[:TAKES_MEDICATION]->(m)
                MERGE (e)-[:HAS_MEDICATION]->(m)
                """,
                enc_id=enc_id,
                pid=pid,
                code=rxnorm,
                name=name,
            )

    print(f"✔ Loaded {len(rows)} medications")


def main():
    print("=== Starting Snowflake → Aura ETL ===")
    totp = input("Enter Snowflake TOTP (6 digits): ").strip()

    conn = None
    driver = None

    try:
        # 1) Connect to Snowflake with MFA
        conn = get_snowflake_conn(totp)
        print("✅ Snowflake connection established")

        # 2) Connect to Neo4j Aura
        driver = get_aura_driver()
        with driver.session(database="neo4j") as s:
            msg = s.run("RETURN 'Connected to Aura ✅' AS msg").single()["msg"]
            print("✅", msg)

        # 3) Run ETL steps in a logical order
        load_patients(conn, driver)
        load_encounters(conn, driver)
        load_conditions(conn, driver)
        load_medications(conn, driver)

        print("\n🎉 ETL Completed! Data is now in Neo4j AuraDB.")

    except Exception as e:
        print("\n❌ ETL failed:", e)

    finally:
        if conn is not None:
            conn.close()
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    main()
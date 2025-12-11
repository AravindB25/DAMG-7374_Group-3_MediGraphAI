import os
from dotenv import load_dotenv
import snowflake.connector
from neo4j import GraphDatabase

# -----------------------------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------------------------
# Let python-dotenv auto-discover .env (current dir or parents)
load_dotenv(override=True)

MAX_ROWS_PER_ENTITY = 7000  # hard cap for each category

REQUIRED_ENV_VARS = [
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_ROLE",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
]


def ensure_env():
    """
    Make sure all required environment variables are present.
    If anything is missing, raise a clear RuntimeError.
    """
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ".\nCheck your .env file and ensure you're running sf_to_aura.py "
              "from the folder where .env is visible."
        )


# -----------------------------------------------------------------------------
# Connections
# -----------------------------------------------------------------------------
def get_snowflake_conn(totp_code: str):
    """
    Open a single Snowflake connection using username + password + TOTP.
    """
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        passcode=totp_code.strip(),
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


# -----------------------------------------------------------------------------
# Helpers for progress / skipping
# -----------------------------------------------------------------------------
def count_nodes(driver, label: str) -> int:
    """
    Return count of nodes with given label in Neo4j.
    """
    with driver.session(database="neo4j") as session:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
        return result.single()["c"]


def already_loaded(driver, label: str) -> bool:
    """
    True if we already have at least 1 node with that label – used to skip ETL step.
    """
    c = count_nodes(driver, label)
    if c > 0:
        print(f"⚠ Found {c} existing `{label}` nodes in Neo4j – skipping load for this category.")
        return True
    return False


# -----------------------------------------------------------------------------
# ETL steps
# -----------------------------------------------------------------------------
def load_patients(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Patient"):
        return

    print(f"\n=== Loading Patients (max {max_rows}) ===")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, SEX, ZIP, AGE
        FROM MEDIGRAPH.PUBLIC.V_PATIENTS
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} patient rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (pid, first, last, sex, zip_code, age) in enumerate(rows, start=1):
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
            if idx % 500 == 0 or idx == total:
                print(f"  → Patients loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Patient records into Neo4j.")


def load_providers(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Provider"):
        return

    print(f"\n=== Loading Providers (max {max_rows}) ===")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT PROVIDER_ID, PROVIDER_NAME, SPECIALTY, STATE, ZIP
        FROM MEDIGRAPH.PUBLIC.V_PROVIDERS
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} provider rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (prov_id, name, specialty, state, zip_code) in enumerate(rows, start=1):
            session.run(
                """
                MERGE (pr:Provider {id: $pid})
                SET pr.name      = $name,
                    pr.specialty = $specialty,
                    pr.state     = $state,
                    pr.zip       = $zip
                """,
                pid=prov_id,
                name=name,
                specialty=specialty,
                state=state,
                zip=str(zip_code) if zip_code is not None else None,
            )
            if idx % 500 == 0 or idx == total:
                print(f"  → Providers loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Provider records into Neo4j.")


def load_encounters(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Encounter"):
        return

    print(f"\n=== Loading Encounters (max {max_rows}) ===")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT ENC_ID, PATIENT_ID, PROVIDER_NPI, START_TIME, END_TIME
        FROM MEDIGRAPH.PUBLIC.V_ENCOUNTERS
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} encounter rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (enc_id, pid, provider_npi, start_time, end_time) in enumerate(rows, start=1):
            session.run(
                """
                MERGE (p:Patient {id: $pid})
                MERGE (e:Encounter {id: $enc_id})
                SET e.start_time   = $start_time,
                    e.end_time     = $end_time,
                    e.provider_npi = $provider_npi
                MERGE (p)-[:HAS_ENCOUNTER]->(e)

                // Link to Provider, using provider_npi as the Provider id
                MERGE (pr:Provider {id: $provider_npi})
                MERGE (e)-[:HAS_PROVIDER]->(pr)
                MERGE (p)-[:HAS_PROVIDER]->(pr)
                """,
                enc_id=enc_id,
                pid=pid,
                provider_npi=provider_npi,
                start_time=str(start_time) if start_time is not None else None,
                end_time=str(end_time) if end_time is not None else None,
            )
            if idx % 500 == 0 or idx == total:
                print(f"  → Encounters loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Encounter records into Neo4j.")


def load_conditions(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Condition"):
        return

    print(f"\n=== Loading Conditions (max {max_rows}) ===")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT ENC_ID, PATIENT_ID, ICD_CODE, NAME
        FROM MEDIGRAPH.PUBLIC.V_CONDITIONS
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} condition rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (enc_id, pid, icd_code, name) in enumerate(rows, start=1):
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
            if idx % 500 == 0 or idx == total:
                print(f"  → Conditions loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Condition records into Neo4j.")


def load_medications(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Medication"):
        return

    print(f"\n=== Loading Medications (max {max_rows}) ===")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT ENC_ID, PATIENT_ID, RXNORM, NAME
        FROM MEDIGRAPH.PUBLIC.V_MEDICATIONS
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} medication rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (enc_id, pid, rxnorm, name) in enumerate(rows, start=1):
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
            if idx % 500 == 0 or idx == total:
                print(f"  → Medications loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Medication records into Neo4j.")


def load_observations(conn, driver, max_rows: int = MAX_ROWS_PER_ENTITY):
    if already_loaded(driver, "Observation"):
        return

    print(f"\n=== Loading Observations (max {max_rows}) ===")
    cur = conn.cursor()
    # Adjust column names if needed to match your OBSERVATIONS table
    cur.execute(
        f"""
        SELECT
            OBSERVATION_ID,
            PATIENT_ID,
            ENCOUNTER_ID,
            DESCRIPTION,
            VALUE,
            UNIT,
            CATEGORY,
            CODE,
            OBS_DATETIME
        FROM MEDIGRAPH.PUBLIC.OBSERVATIONS
        WHERE OBSERVATION_ID IS NOT NULL
        ORDER BY OBS_DATETIME
        LIMIT {max_rows}
        """
    )
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"Snowflake returned {total} observation rows (capped at {max_rows}).")

    with driver.session(database="neo4j") as session:
        for idx, (
            obs_id,
            pid,
            enc_id,
            desc,
            value,
            unit,
            category,
            code,
            obs_dt,
        ) in enumerate(rows, start=1):
            if obs_id is None or pid is None:
                continue

            session.run(
                """
                MERGE (p:Patient {id: $pid})
                MERGE (o:Observation {id: $obs_id})
                SET
                    o.description  = $description,
                    o.value        = $value,
                    o.unit         = $unit,
                    o.category     = $category,
                    o.code         = $code,
                    o.obs_datetime = $obs_dt
                MERGE (p)-[:HAS_OBSERVATION]->(o)

                // Optional: attach to encounter if present
                FOREACH (encId IN CASE WHEN $enc_id IS NULL THEN [] ELSE [$enc_id] END |
                  MERGE (e:Encounter {id: encId})
                  MERGE (e)-[:HAS_OBSERVATION]->(o)
                )
                """,
                obs_id=str(obs_id),
                pid=str(pid),
                enc_id=str(enc_id) if enc_id is not None else None,
                description=desc,
                value=float(value) if value is not None else None,
                unit=unit,
                category=category,
                code=code,
                obs_dt=str(obs_dt) if obs_dt is not None else None,
            )

            if idx % 500 == 0 or idx == total:
                print(f"  → Observations loaded: {idx}/{total}")

    print(f"✔ Finished loading {total} Observation records into Neo4j.")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    print("=== Starting Snowflake → Aura ETL (demo-friendly) ===")

    # 0) Validate environment
    try:
        ensure_env()
    except RuntimeError as e:
        print("❌ Config error:", e)
        return

    totp = input("Enter Snowflake TOTP (6 digits): ").strip()

    conn = None
    driver = None

    try:
        # 1) Connect to Snowflake
        conn = get_snowflake_conn(totp)
        print("✅ Snowflake connection established")

        # 2) Connect to Neo4j Aura
        driver = get_aura_driver()
        with driver.session(database="neo4j") as s:
            msg = s.run("RETURN 'Connected to Aura ✅' AS msg").single()["msg"]
            print("✅", msg)

        # 3) Run ETL steps in logical order
        load_patients(conn, driver)
        load_providers(conn, driver)
        load_encounters(conn, driver)
        load_conditions(conn, driver)
        load_medications(conn, driver)
        load_observations(conn, driver)

        print(
            "\n🎉 ETL Completed! (Each category capped at "
            f"{MAX_ROWS_PER_ENTITY} rows and skipped if already present.)"
        )

    except Exception as e:
        print("\n❌ ETL failed:", e)

    finally:
        if conn is not None:
            conn.close()
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    main()
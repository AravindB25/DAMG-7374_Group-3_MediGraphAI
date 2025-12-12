# DAMG 7374 - GROUP 3 - MediGraph AI  
### *Intelligent Healthcare Knowledge Graph with LLM Integration*

---

## 👥 Team Members
- **Aravind Balaji**
- **Sai Manasa Karanam**
- **Varun Tadimeti**

---

🧑‍💻 Team Members & Contributions

Aravind Balaji
• Led overall system architecture and end-to-end integration
• Designed and implemented the Snowflake → Neo4j AuraDB ETL pipeline with MFA/TOTP authentication
• Built the Neo4j healthcare knowledge graph schema (Patients, Encounters, Conditions, Medications, Providers, Observations)
• Developed the Streamlit application (dashboards, graph visualization, NL Q&A, LLM-powered Cypher generation)
• Integrated Observations and Evaluation modules based on professor feedback
• Implemented NER-ready pipeline and guideline linking framework
• Led testing, debugging, demo preparation, and final presentation

⸻

Sai Manasa Karanam
• Designed and implemented Snowflake database schemas and analytical views
• Loaded and validated Synthea EHR datasets in Snowflake
• Created optimized Snowflake views for Patients, Encounters, Conditions, Medications, Providers, and Observations
• Ensured data normalization, quality checks, and query performance in Snowflake

⸻

Varun Tadimeti
• Designed and implemented the Neo4j graph data model
• Created node labels, relationships, and constraints for healthcare entities
• Developed and optimized Cypher queries for graph traversal and analytics
• Validated semantic correctness of the Neo4j knowledge graph and supported AuraDB deployment

## 📘 Overview
**MediGraph AI** is an intelligent clinical analytics platform that transforms structured EHR data from **Snowflake** into a connected **Neo4j AuraDB Knowledge Graph**, visualized through an interactive **Streamlit** application.

The system supports semantic exploration of:
- **Patients**
- **Encounters**
- **Conditions**
- **Medications**
- **Providers**
- **Observations**

It also provides **LLM-powered Cypher generation**, **Guideline linking**, and **NER-based concept extraction**, forming the foundation for **GraphRAG**-style clinical reasoning.

---

## 🚀 Key Features

### 🔹 ETL Pipeline (Python + Snowflake)
- Loads Synthea EHR datasets:
  - Patients, Providers, Encounters  
  - Conditions, Medications, Observations  
- Automatically caps ingestion (e.g., 7000 per entity) for fast demos  
- Skips already-loaded entities  
- Shows progress during ingestion  
- Secure **MFA/TOTP** login to Snowflake  

---

### 🔹 Knowledge Graph Construction (Neo4j AuraDB)
- Converts relational EHR tables into a healthcare semantic graph  
- Creates relationships:
  - `(Patient)-[:HAS_CONDITION]->(Condition)`
  - `(Patient)-[:TAKES_MEDICATION]->(Medication)`
  - `(Patient)-[:HAS_ENCOUNTER]->(Encounter)`
  - `(Encounter)-[:HAS_PROVIDER]->(Provider)`
  - `(Encounter)-[:HAS_OBSERVATION]->(Observation)`
  - `(Patient)-[:HAS_OBSERVATION]->(Observation)`
- Fully deployable to **AuraDB Cloud**

---

### 🔹 Interactive UI (Streamlit)
- Clean sidebar authentication & connection  
- Entity dashboards with sample data  
- Graph viewer (Pyvis)  
- Observations explorer  
- **Evaluation module** detecting data completeness, missing attributes, etc.  

---

### 🔹 LLM-Powered Cypher Q&A
- Converts natural-language questions ➜ valid Cypher queries  
- Supports all entity types:
  **Patients, Conditions, Encounters, Providers, Medications, Observations**
- Clearly displays generated Cypher  
- Executes queries on AuraDB and shows results  
- Graceful fallback (no crashes, no blank errors)

---

### 🔹 Guidelines + NER Module
- Text box: *“Paste a clinical note”*  
- Extracts condition concepts (NER-ready for Gemini 3.0)  
- Links extracted concepts to guideline nodes (if seeded in graph)  
- Shows demo guidelines when graph data is missing  

---

## 🧩 Tech Stack

| Layer | Technology |
|------|------------|
| Database (Structured) | **Snowflake Warehouse** |
| Graph Database | **Neo4j → AuraDB Cloud** |
| UI / Visualization | **Streamlit + Pyvis** |
| Backend / ETL | Python 3.12, `pandas`, `snowflake-connector-python`, `neo4j-driver` |
| LLM | **OpenAI GPT (Cypher Generator)** |
| Authentication | **MFA (TOTP via Google Authenticator)** |
| Env Mgmt | `python-dotenv`, `venv` |

---


## 🧠 Project Architecture  
**Snowflake (ETL + Views)** ➜ **Python Connector** ➜ **Neo4j Graph Model** ➜ **Streamlit UI** ➜ *(LLM Module future)*  

---
---

## 🧭 Milestones Achieved

- ✅ Snowflake ETL & View Creation  
- ✅ Secure MFA Authentication  
- ✅ Neo4j Schema Design & Seeding  
- ✅ Added Observations into graph  
- ✅ Streamlit Dashboards + Graph Visualizer  
- ✅ NL Q&A (rule-based)  
- ✅ LLM-based Cypher Generator  
- ✅ Guidelines + NER Module  
- ✅ Dataset Evaluation Module  
- ✅ Incorporated professor feedback (Added Observations,Evaluations, improve linking, expand Q&A)
- ✅ Project completed as per initial scope and ready for final presentation/demo.
---

## ⚙️ How to Run

```bash
# Clone repository
git clone https://github.com/<your-username>/MediGraphAI.git
cd MediGraphAI

# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py

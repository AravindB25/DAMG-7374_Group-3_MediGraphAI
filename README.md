# DAMG 7374 - GROUP 3 - MediGraph AI  
### *Intelligent Healthcare Knowledge Graph with LLM Integration*

## 👥 Team Members  
- **Aravind Balaji**  
- **Sai Manasa Karanam**  
- **Varun Tadimeti**

---

## 📘 Overview  
**MediGraph AI** is an intelligent healthcare analytics platform that integrates structured clinical data from **Snowflake** and converts it into a connected **Neo4j Knowledge Graph**, visualized and queried through a **Streamlit** web interface.  
It enables semantic exploration of patient data—conditions, medications, and encounters—while paving the path toward **LLM-powered clinical reasoning** and **GraphRAG-based question answering**.

---

## 🚀 Key Features  
- **ETL Pipeline (Python + Snowflake)**  
  - Loads and normalizes *Synthea EHR* datasets (Patients, Providers, Encounters, Conditions, Medications).  
  - Creates analytical views for fast aggregation and filtering.

- **Graph Construction (Neo4j Desktop → AuraDB)**  
  - Transforms relational entities into labeled nodes and relationships.  
  - Links Patients → Conditions → Medications → Encounters → Providers.  
  - Supports migration to **Neo4j AuraDB** for cloud-based deployment.

- **Interactive UI (Streamlit)**  
  - Secure **MFA/TOTP** authentication for Snowflake access.  
  - Query and visualize patient-condition networks with a **Pyvis** graph viewer.  
  - Simple **natural-language Q&A** for graph exploration.  

- **Future Extension**  
  - Integration of **LLM modules** for semantic question understanding and **GraphRAG** reasoning.  

---

## 🧩 Tech Stack  
| Layer | Technology |
|-------|-------------|
| Database (Structured) | **Snowflake Warehouse** |
| Graph Database | **Neo4j → Neo4j AuraDB Cloud** |
| Visualization & UI | **Streamlit + Pyvis** |
| Language / ETL | **Python 3.12**, `pandas`, `neo4j`, `snowflake-connector-python` |
| Environment Mgmt | `python-dotenv`, `venv` |
| Authentication | **MFA (TOTP via Google Authenticator)** |

---

## 🧠 Project Architecture  
**Snowflake (ETL + Views)** ➜ **Python Connector** ➜ **Neo4j Graph Model** ➜ **Streamlit UI** ➜ *(LLM Module future)*  

---

## 🧭 Milestones Achieved  
1. ✅ Snowflake ETL & View Creation  
2. ✅ Secure MFA Authentication  
3. ✅ Neo4j Schema Design & Graph Seeding  
4. ✅ Streamlit Integration with Q&A and Visualization  
5. ✅ Migration from Neo4j Desktop to AuraDB Cloud
6. ✅ Successful Professor Demo and Feedback (Next: Add LLM Integration)  

---

## ⚙️ How to Run  
```bash
git clone https://github.com/<your-username>/MediGraphAI.git
cd MediGraphAI
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py

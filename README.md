<a name="readme-top"></a>

<div align="center">
  <h1 style="border-bottom: none;">
    <b>Prometheus</b><br>
  </h1>
</div>


## 📖 Overview

Prometheus is a research-backed, production-ready platform that leverages **unified knowledge graphs** and **multi-agent systems** to perform intelligent operations on multilingual codebases. Built on LangGraph state machines, it orchestrates specialized AI agents to automatically classify issues, reproduce bugs, retrieve relevant context, and generate validated patches.

### Key Capabilities

- **Automated Issue Resolution**: End-to-end bug fixing with reproduction, patch generation, and multi-level validation
- **Feature Implementation Pipeline**: Context-aware feature request analysis, implementation planning, and code generation with optional regression testing
- **Intelligent Context Retrieval**: Graph-based semantic search over codebase structure, AST, and documentation
- **Multi-Agent Orchestration**: Coordinated workflow between classification, reproduction, and resolution agents
- **Knowledge Graph Integration**: Neo4j-powered unified representation of code structure and semantics
- **Containerized Execution**: Docker-isolated testing and validation environment
- **Question Answering**: Natural language queries with tool-augmented LLM agents

📖 **[Multi-Agent Architecture](docs/Multi-Agent-Architecture.md)**

---

## 🏗️ Architecture

Prometheus implements a hierarchical multi-agent system:

```
                              User Issue
                                  |
                                  v
                ┌─────────────────────────────────┐
                │  Issue Classification Agent     │
                │  (bug/question/feature/doc)     │
                └─────────────┬───────────────────┘
                              |
              ┌───────────────┼───────────────┐
              |               |               |
              v               v               v
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │Bug Pipeline  │  │Feature       │  │Question      │
    │              │  │Pipeline      │  │Pipeline      │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           |                 |                 |
           v                 v                 v
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │Bug           │  │Feature       │  │Context       │
    │Reproduction  │  │Analysis      │  │Retrieval     │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           |                 |                 |
           v                 v                 v
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │Issue         │  │Patch         │  │Question      │
    │Resolution    │  │Generation    │  │Analysis      │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           |                 |                 |
           └─────────────────┼─────────────────┘
                             v
                      Response Generation
```

**Core Components**:
- **Knowledge Graph**: Tree-sitter-based AST and semantic code representation in Neo4j
- **LangGraph State Machines**: Coordinated multi-agent workflows with checkpointing
- **Docker Containers**: Isolated build and test execution environments
- **LLM Integration**: Multi-tier model strategy (GPT-4, Claude, Gemini support)

See **[Architecture Documentation](docs/Multi-Agent-Architecture.md)** for details.

---

## ⚡ Quick Start

### ✅ Prerequisites

- **Docker** and **Docker Compose**
- **Python 3.11+** (for local development)
- **API Keys**: OpenAI, Anthropic, or Google Gemini

### 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/EuniAI/Prometheus.git
   cd Prometheus
   ```

2. **Configure environment**
   ```bash
   cp example.env .env
   # Edit .env with your API keys
   ```

3. **Generate JWT secret** (required for authentication)
   ```bash
   python -m prometheus.script.generate_jwt_token
   # Copy output to .env as PROMETHEUS_JWT_SECRET_KEY
   ```

4. **Create working directory**
   ```bash
   mkdir -p working_dir
   ```

5. **Start services**
   ```bash
   docker-compose up --build
   ```

6. **Access the platform**
   - API: [http://localhost:9002/v1.2](http://localhost:9002/v1.2)
   - Interactive Docs: [http://localhost:9002/docs](http://localhost:9002/docs)

---

## 💻 Development

### 🛠️ Local Setup

```bash
# Install dependencies
pip install hatchling
pip install .
pip install .[test]

# Run development server
uvicorn prometheus.app.main:app --host 0.0.0.0 --port 9002 --reload
```

### 🧪 Testing

```bash
# Run tests (excluding git-dependent tests)
coverage run --source=prometheus -m pytest -v -s -m "not git"

# Generate coverage report
coverage report -m
coverage html
open htmlcov/index.html
```

### 🗄️ Database Setup

**PostgreSQL** (required for state checkpointing):
```bash
docker run -d \
  -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=postgres \
  postgres
```

**Neo4j** (required for knowledge graph):
```bash
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_dbms_memory_heap_initial__size=4G \
  -e NEO4J_dbms_memory_heap_max__size=8G \
  neo4j
```

Verify at [http://localhost:7474](http://localhost:7474)

---

## 📜 License

- **Community Edition**: Licensed under the [GNU General Public License v3.0 (GPLv3)](https://www.gnu.org/licenses/gpl-3.0.html).  
  You are free to use, modify, and redistribute this code, provided that any derivative works are also released under the GPLv3.  
  This ensures the project remains open and contributions benefit the community.

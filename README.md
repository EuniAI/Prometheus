<a name="readme-top"></a>

<div align="center">
  <img src="./docs/static/images/icon.jpg" alt="Prometheus Logo" width="200">
  <h1 align="center">Prometheus</h1>
  <p align="center">
    <strong>AI-Powered Codebase Intelligence Platform</strong>
  </p>
  <p align="center">
    Automated issue resolution, intelligent code analysis, and multi-agent orchestration for modern software development
  </p>
</div>

<div align="center">
  <a href="https://github.com/EuniAI/Prometheus/graphs/contributors"><img src="https://img.shields.io/github/contributors/EuniAI/Prometheus?style=for-the-badge&color=blue" alt="Contributors"></a>
  <a href="https://github.com/EuniAI/Prometheus/stargazers"><img src="https://img.shields.io/github/stars/EuniAI/Prometheus?style=for-the-badge&color=blue" alt="Stargazers"></a>
  <a href="https://www.arxiv.org/abs/2507.19942"><img src="https://img.shields.io/badge/Paper-arXiv-red?style=for-the-badge&logo=arxiv" alt="Paper"></a>
  <br/>
  <a href="https://github.com/EuniAI/Prometheus/blob/main/CREDITS.md"><img src="https://img.shields.io/badge/Project-Credits-blue?style=for-the-badge&color=FFE165&logo=github&logoColor=white" alt="Credits"></a>
  <a href="https://discord.gg/jDG4wqkKZj"><img src="https://img.shields.io/badge/Discord-Join%20Us-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>

  <br/>
  <hr>
</div>

<br/>

## Overview

Prometheus is a research-backed, production-ready platform that leverages **unified knowledge graphs** and **multi-agent systems** to perform intelligent operations on multilingual codebases. Built on LangGraph state machines, it orchestrates specialized AI agents to automatically classify issues, reproduce bugs, retrieve relevant context, and generate validated patches.

### Key Capabilities

- **Automated Issue Resolution**: End-to-end bug fixing with reproduction, patch generation, and multi-level validation
- **Intelligent Context Retrieval**: Graph-based semantic search over codebase structure, AST, and documentation
- **Multi-Agent Orchestration**: Coordinated workflow between classification, reproduction, and resolution agents
- **Knowledge Graph Integration**: Neo4j-powered unified representation of code structure and semantics
- **Containerized Execution**: Docker-isolated testing and validation environment
- **Question Answering**: Natural language queries with tool-augmented LLM agents

📖 **[Multi-Agent Architecture](docs/Multi-Agent-Architecture.md)** | 📄 **[Research Paper](https://arxiv.org/abs/2507.19942)**

---

## Architecture

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
              ┌───────────────┴───────────────┐
              |                               |
              v                               v
    ┌──────────────────┐            ┌──────────────────┐
    │   Bug Pipeline   │            │ Question Pipeline│
    └────────┬─────────┘            └────────┬─────────┘
             |                               |
             v                               v
    ┌──────────────────┐            ┌──────────────────┐
    │ Bug Reproduction │            │ Context Retrieval│
    │      Agent       │            │      Agent       │
    └────────┬─────────┘            └────────┬─────────┘
             |                               |
             v                               v
    ┌──────────────────┐            ┌──────────────────┐
    │ Issue Resolution │            │ Question Analysis│
    │      Agent       │            │      Agent       │
    └────────┬─────────┘            └────────┬─────────┘
             |                               |
             └───────────────┬───────────────┘
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

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose**
- **Python 3.11+** (for local development)
- **API Keys**: OpenAI, Anthropic, or Google Gemini

### Installation

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
   # Linux
   docker-compose up --build

   # macOS/Windows (requires manual PostgreSQL setup)
   docker-compose -f docker-compose.win_mac.yml up --build
   ```

6. **Access the platform**
   - API: [http://localhost:9002/v1.2](http://localhost:9002/v1.2)
   - Interactive Docs: [http://localhost:9002/docs](http://localhost:9002/docs)

---

## Development

### Local Setup

```bash
# Install dependencies
pip install hatchling
pip install .
pip install .[test]

# Run development server
uvicorn prometheus.app.main:app --host 0.0.0.0 --port 9002 --reload
```

### Testing

```bash
# Run tests (excluding git-dependent tests)
coverage run --source=prometheus -m pytest -v -s -m "not git"

# Generate coverage report
coverage report -m
coverage html
open htmlcov/index.html
```

### Database Setup

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

## Research & Citation

Prometheus is based on peer-reviewed research on unified knowledge graphs for multilingual code analysis.

```bibtex
@misc{prometheus2025,
  title={Prometheus: Unified Knowledge Graphs for Issue Resolution in Multilingual Codebases},
  author={Zimin Chen and Yue Pan and Siyu Lu and Jiayi Xu and Claire Le Goues and Martin Monperrus and He Ye},
  year={2025},
  eprint={2507.19942},
  archivePrefix={arXiv},
  primaryClass={cs.SE},
  url={https://arxiv.org/abs/2507.19942}
}
```

---

## Contributing

We welcome contributions! Please see our [contributing guidelines](CONTRIBUTING.md) for details.

- Report bugs via [GitHub Issues](https://github.com/EuniAI/Prometheus/issues)
- Submit feature requests and improvements via Pull Requests
- Join discussions on [Discord](https://discord.gg/jDG4wqkKZj)

---

## License

This project is dual-licensed:
- **Community Edition**: Licensed under the [GNU General Public License v3.0 (GPLv3)](https://www.gnu.org/licenses/gpl-3.0.html).  
  You are free to use, modify, and redistribute this code, provided that any derivative works are also released under the GPLv3.  
  This ensures the project remains open and contributions benefit the community.

- **Commercial Edition**: For organizations that wish to use this software in **proprietary, closed-source, or commercial settings**,  
  a separate commercial license is available. Please contact **EUNI.AI Team** to discuss licensing terms.

---

## Support

- **Documentation**: [Multi-Agent Architecture](docs/Multi-Agent-Architecture.md) | [GitHub Issue Debug Guide](docs/GitHub-Issue-Debug-Guide.md)
- **Community**: [Discord Server](https://discord.gg/jDG4wqkKZj)
- **Email**: business@euni.ai
- **Issues**: [GitHub Issues](https://github.com/EuniAI/Prometheus/issues)

---

## Acknowledgments

<div align="center">
  <img src="./docs/static/images/delysium_logo.svg" alt="Delysium Logo" width="150">
</div>

We thank [Delysium](https://delysium.com) for their support in organizing LLM-related resources, architecture design, and optimization, which greatly strengthened our research infrastructure and capabilities.

---

<div align="center">
  <p>Made with ❤️ by the <a href="https://euni.ai/">EuniAI</a> Team</p>
  <p>
    <a href="#readme-top">Back to top ↑</a>
  </p>
</div>
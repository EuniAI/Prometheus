# Multi-Agent Architecture

Prometheus uses a multi-agent system powered by LangGraph to intelligently process and resolve GitHub issues. Each agent is specialized for a specific task in the issue resolution pipeline.

## Agent Overview

### 1. Issue Classification Agent

**Purpose**: Automatically classifies GitHub issues into categories (bug, question, feature, documentation).

**Location**: `prometheus/lang_graph/subgraphs/issue_classification_subgraph.py`

**Workflow**:
- Retrieves relevant code context from the knowledge graph
- Uses LLM to analyze issue content and classify type
- Returns issue type for routing to appropriate handler

**When Used**: When `issue_type == "auto"` in the issue request

---

### 2. Environment Build Agent

**Status**: In Progress

**Purpose**: Automatically sets up and configures the development environment for testing and building.

**Planned Features**:
- Auto-detect project type (Python, Node.js, Java, etc.)
- Install dependencies
- Configure build tools
- Validate environment setup

---

### 3. Bug Reproduction Agent

**Purpose**: Attempts to reproduce reported bugs by writing and executing reproduction tests.

**Location**: `prometheus/lang_graph/subgraphs/bug_reproduction_subgraph.py`

**Workflow**:
1. Retrieves bug-related code context from knowledge graph
2. Generates reproduction test code using LLM
3. Edits necessary files to create the test
4. Executes the test in a Docker container
5. Evaluates whether the bug was successfully reproduced
6. Retries with feedback if reproduction fails

**Output**:
- `reproduced_bug`: Boolean indicating success
- `reproduced_bug_file`: Path to reproduction test
- `reproduced_bug_commands`: Commands to reproduce
- `reproduced_bug_patch`: Git patch with changes

**Key Features**:
- Iterative refinement with retry loops
- Docker-isolated execution
- Feedback-driven improvement

---

### 4. Context Retrieval Agent

**Purpose**: Retrieves relevant code and documentation context from the Neo4j knowledge graph.

**Location**: `prometheus/lang_graph/subgraphs/context_retrieval_subgraph.py`

**Workflow**:
1. Converts natural language query to knowledge graph query
2. Uses LLM with graph traversal tools to find relevant context
3. Selects and extracts useful code snippets
4. Optionally refines query and retries if context is insufficient
5. Returns structured context (code, AST nodes, documentation)

**Key Features**:
- Iterative query refinement (2-4 loops)
- Tool-augmented LLM with Neo4j access
- Traverses file hierarchy, AST structure, and text chunks

**Used By**: All other agents for context gathering

---

### 5. Issue Resolution Agent

**Purpose**: Generates and validates bug fix patches for verified bugs.

**Location**: `prometheus/lang_graph/subgraphs/issue_verified_bug_subgraph.py`

**Workflow**:
1. Retrieves fix-relevant code context
2. Analyzes bug root cause using LLM
3. Generates code patch to fix the bug
4. Applies patch and creates git diff
5. Validates patch against:
   - Reproduction test (must pass)
   - Regression tests (optional)
   - Existing test suite (optional)
6. Generates multiple candidate patches
7. Selects best patch based on test results
8. Retries with error feedback if tests fail

**Output**:
- `edit_patch`: Final selected fix patch
- Test pass/fail results

**Key Features**:
- Multi-candidate patch generation
- Multi-level validation (reproduction, regression, existing tests)
- Feedback-driven iteration
- Best patch selection using LLM

---

## Agent Coordination

### Main Issue Processing Flow

```
User Issue -> Issue Classification Agent
              |
      [Route by issue type]
              |
        +-----+-----+
        |           |
      BUG       QUESTION
        |           |
        v           v
  Bug Pipeline  Question Pipeline
```

### Bug Resolution Pipeline

```
Bug Issue -> Context Retrieval Agent (select regression tests)
          -> Bug Reproduction Agent (verify bug exists)
          -> [If reproduced] -> Issue Resolution Agent (generate fix)
          -> [If not reproduced] -> Direct resolution without reproduction
          -> Response Generation
```

### Question Answering Pipeline

```
Question -> Context Retrieval Agent (gather relevant code/docs)
         -> Question Analysis Agent (LLM with tools)
         -> Response Generation
```

---

## Agent Communication

Agents communicate through **shared state** managed by LangGraph:

- Each subgraph has a typed state dictionary
- State flows through nodes and is updated progressively
- Parent states are inherited by child subgraphs
- Results are passed back through state returns

---

## Technology Stack

- **LangGraph**: State machine orchestration
- **LangChain**: LLM integration and tool calling
- **Neo4j**: Knowledge graph storage and retrieval
- **Docker**: Isolated test execution environment
- **Tree-sitter**: Code parsing and AST generation
- **Git**: Patch management and version control

---

## Future Enhancements

- **Environment Build Agent**: Complete implementation for automatic setup
- **Pull Request Review Agent**: Automated code review
- **Feature Implementation Agent**: Handle feature requests
- **Documentation Generation Agent**: Auto-generate docs from code
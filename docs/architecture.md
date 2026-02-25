# Architecture

System architecture for the ate-arch experiment harness.

## 1. Experiment Protocol Flow

End-to-end flow from experiment setup to statistical analysis.

```mermaid
flowchart TD
    subgraph Setup
        A[Define scenario + stakeholders] --> B[Configure partitions A/B/C]
        B --> C[Scaffold run directories]
    end

    subgraph Execution["Execution (per run)"]
        C --> D[Launch Claude Code session]
        D --> E{Architecture condition?}
        E -->|Control| F[Hub-and-spoke: lead dispatches subagents]
        E -->|Treatment| G[Symmetric peers with SendMessage]
        F --> H[Agents interview stakeholders via LLM simulator]
        G --> H
        H --> I[Produce architecture document]
    end

    subgraph Scoring
        I --> J[L1: Constraint discovery checklist]
        I --> K[L2: Conflict identification checklist]
        I --> L[L3: Resolution quality - LLM-as-judge]
        I --> M[L4: Hidden dependency checklist]
        J & K & L & M --> N[Composite score]
    end

    subgraph Analysis
        I --> O[Communication analysis]
        N --> P[Statistical tests]
        O --> P
        P --> Q[Findings report]
    end
```

## 2. System Boundaries

External systems and their interfaces with the ate-arch harness.

```mermaid
flowchart LR
    subgraph External
        CC["Claude Code<br/>(Opus 4.6)"]
        API_SIM["Claude API<br/>(Haiku 4.5)<br/>Stakeholder sim"]
        API_SCORE["Claude API<br/>(Sonnet 4.6)<br/>Scoring"]
        FS["Filesystem<br/>data/"]
    end

    subgraph ate-arch["ate-arch harness"]
        CLI["cli.py<br/>Typer CLI"]
        HAR["harness.py<br/>Scaffolding"]
        SIM["simulator.py<br/>Stakeholder sim"]
        SCO["scoring.py<br/>4-layer rubric"]
        COM["comms.py<br/>Comm analysis"]
        BAT["batch.py<br/>Batch ops"]
    end

    CLI --> HAR
    CLI --> SIM
    CLI --> SCO
    CLI --> COM
    CLI --> BAT

    HAR -->|scaffold dirs| FS
    SIM -->|interview calls| API_SIM
    SCO -->|L3 judgments| API_SCORE
    COM -->|read transcripts| FS

    CC -->|produces| FS
    CC -->|calls interview tool| SIM
```

## 3. Module Dependency Graph

Internal import dependencies between Python modules.

```mermaid
flowchart BT
    models["models.py<br/>Pydantic models"]
    config["config.py<br/>YAML loading"]
    simulator["simulator.py<br/>LLM stakeholder sim"]
    harness["harness.py<br/>Scaffolding + state"]
    scoring["scoring.py<br/>4-layer rubric"]
    batch["batch.py<br/>Batch scaffold + verify"]
    comms["comms.py<br/>Communication analysis"]
    cli["cli.py<br/>Typer CLI entry point"]

    config --> models
    simulator --> models
    simulator --> config
    harness --> models
    harness --> config
    scoring --> models
    scoring --> simulator
    batch --> models
    batch --> harness

    cli --> models
    cli --> config
    cli --> simulator
    cli --> harness
    cli --> scoring
    cli --> batch
    cli --> comms

    style models fill:#e1f5fe
    style cli fill:#fff3e0
    style comms fill:#f3e5f5
```

`models.py` is the foundation (zero internal dependencies). `cli.py` is the
hub (imports all modules). `comms.py` is standalone (no internal dependencies).

## 4. Data Flow

How data moves through the system during a complete experiment run.

```mermaid
flowchart LR
    subgraph Config["config/"]
        SC[scenarios/]
        ST[stakeholders/]
        PA[partitions.yaml]
        CO[conflicts.yaml]
        RU[rubric.yaml]
    end

    subgraph Harness["harness.py"]
        SCAFFOLD[scaffold_run]
    end

    subgraph DataRuns["data/runs/{run_id}/"]
        SG[session_guide.md]
        IS[interview_state.json]
        MD[metadata.json]
        ARCH[architecture.md]
    end

    subgraph DataOut["data/"]
        TR[transcripts/*.jsonl]
        SCORES[scores/*_sonnet.json]
        COMMS[comms/*_comms.json]
    end

    SC & ST & PA --> SCAFFOLD
    SCAFFOLD --> SG & MD

    SG -->|human feeds to| CC["Claude Code session"]
    CC -->|interviews via| SIM["simulator.py"]
    SIM --> IS
    CC --> ARCH
    CC --> TR

    ARCH --> SCORING["scoring.py"]
    CO & RU --> SCORING
    SCORING --> SCORES

    TR --> COMMS_PY["comms.py"]
    COMMS_PY --> COMMS
```

## 5. Experimental Design: 2x2 Matrix

The experiment crosses 2 architecture conditions with 2 partition conditions
(Partition B was designed but not executed).

```
                    Partition A              Partition C
                    (25% cross)              (75% cross)
                ┌─────────────────┬─────────────────────┐
                │                 │                     │
   Control      │  Control-A      │  Control-C          │
   (hub-spoke)  │  Most conflicts │  Most conflicts     │
                │  within-agent   │  cross-agent        │
                │  Mean: 0.81     │  Mean: 0.84         │
                ├─────────────────┼─────────────────────┤
                │                 │                     │
   Treatment    │  Treatment-A    │  Treatment-C        │
   (peers)      │  Peers can talk │  Peers NEED to talk │
                │  but don't need │  for most conflicts │
                │  Mean: 0.88     │  Mean: 0.91         │
                └─────────────────┴─────────────────────┘
```

### Partition A: 6 within, 2 cross

```mermaid
graph LR
    subgraph Agent-1["Agent 1 (Governance)"]
        CSO["CSO"]
        COM["Compliance"]
        EU["EU Ops"]
    end
    subgraph Agent-2["Agent 2 (Builder)"]
        APAC["APAC Ops"]
        ARCH["Architect"]
        PM["PM"]
    end

    CSO ---|C1| COM
    CSO ---|C2| EU
    COM ---|C3| EU
    APAC ---|C6| ARCH
    APAC ---|C7| PM
    ARCH ---|C8| PM

    COM -.-|C4| APAC
    EU -.-|C5| ARCH

    linkStyle 6 stroke:red,stroke-dasharray:5
    linkStyle 7 stroke:red,stroke-dasharray:5
```

### Partition C: 2 within, 6 cross

```mermaid
graph LR
    subgraph Agent-1["Agent 1"]
        CSO["CSO"]
        COM["Compliance"]
        ARCH["Architect"]
    end
    subgraph Agent-2["Agent 2"]
        EU["EU Ops"]
        APAC["APAC Ops"]
        PM["PM"]
    end

    CSO ---|C1| COM
    APAC ---|C7| PM

    CSO -.-|C2| EU
    COM -.-|C3| EU
    COM -.-|C4| APAC
    EU -.-|C5| ARCH
    APAC -.-|C6| ARCH
    ARCH -.-|C8| PM

    linkStyle 2 stroke:red,stroke-dasharray:5
    linkStyle 3 stroke:red,stroke-dasharray:5
    linkStyle 4 stroke:red,stroke-dasharray:5
    linkStyle 5 stroke:red,stroke-dasharray:5
    linkStyle 6 stroke:red,stroke-dasharray:5
    linkStyle 7 stroke:red,stroke-dasharray:5
```

Solid lines = within-partition conflicts (resolvable by a single agent).
Dashed red lines = cross-partition conflicts (require cross-agent information).

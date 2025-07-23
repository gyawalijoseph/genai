# Spec Generation Flow Diagram

```mermaid
flowchart TD
    %% User Interface
    A[User Input<br/>- Codebase Name<br/>- Vector Results Count] --> B{Form Validation}
    B -->|Valid| C[generate_spec Function]
    B -->|Invalid| D[Show Error Messages]

    %% Main Process Flow
    C --> E[Server Info Extraction]
    C --> F[Database Info Processing]
    C --> G[Address Extraction]
    
    %% Server Info Branch
    E --> E1[Vector Search<br/>codebase + '-external-files'<br/>Query: 'server host']
    E1 --> E2[POST /vector-search<br/>localhost:5000]
    E2 --> E3[similarity_search_pgvector<br/>PGVector Database]
    E3 --> E4[Server_LLM_Extraction<br/>LLM Analysis]
    E4 --> E5[POST /LLM-API<br/>localhost:8082]
    E5 --> E6[safechain_llm_call<br/>llama-3 model]
    E6 --> E7[Extract Host/Port/DB Info]
    E7 --> JSON1[Add to JSON Document<br/>'Server Information']

    %% Database Info Branch
    F --> F1[Two Parallel Vector Searches]
    F1 --> F1A[Internal Search<br/>vector_search(codebase)]
    F1 --> F1B[External Search<br/>vector_search(codebase + '-external-files')]
    
    F1A --> F2[SQL_DB_Extraction_v2<br/>Internal Data]
    F1B --> F3[SQL_DB_Extraction_v2<br/>External Data]
    
    F2 --> F4[SQL Query Detection Loop]
    F3 --> F4
    
    F4 --> F5{SQL Present?<br/>LLM Check}
    F5 -->|No| F6[Skip File]
    F5 -->|Yes| F7[Extract SQL Queries<br/>LLM Call]
    
    F7 --> F8[Validate SQL Queries<br/>LLM Call]
    F8 --> F9{Valid SQL?}
    F9 -->|No| F10[Mark as Invalid]
    F9 -->|Yes| F11[Extract Table/Column Info<br/>LLM Call]
    
    F11 --> F12[HTML Table Extraction]
    F12 --> JSON2[Add to JSON Document<br/>'Database Information']
    F10 --> JSON2
    F6 --> F4

    %% Address Extraction Branch
    G --> G1[get_addresses Function<br/>⚠️ Not Implemented]
    G1 --> JSON3[Add to JSON Document<br/>'Addresses' & 'Dependent Addresses']

    %% Final Steps
    JSON1 --> H[Compile Final JSON]
    JSON2 --> H
    JSON3 --> H
    
    H --> I[Display Summary<br/>Streamlit Interface]
    I --> J[commit_json<br/>Push to GitHub]
    
    %% Backend Services
    subgraph "Backend Services"
        K[Flask App - Port 5000<br/>Vector Search Service]
        L[Flask App - Port 8082<br/>LLM Processing Service]
        M[PGVector Database<br/>Embedding Storage]
        N[LangChain + llama-3<br/>LLM Model]
    end
    
    E2 -.-> K
    F1A -.-> K
    F1B -.-> K
    K -.-> M
    E5 -.-> L
    F5 -.-> L
    F7 -.-> L
    F8 -.-> L
    F11 -.-> L
    L -.-> N

    %% Styling
    classDef userInput fill:#e1f5fe
    classDef processing fill:#f3e5f5
    classDef backend fill:#e8f5e8
    classDef output fill:#fff3e0
    classDef error fill:#ffebee

    class A,B userInput
    class C,E,F,G,E1,E4,F4,F5,F7,F8,F9,F11,F12,G1 processing
    class E2,E5,K,L,M,N backend
    class H,I,J,JSON1,JSON2,JSON3 output
    class D,F6,F10 error
```

## Flow Description

### 1. User Interface Layer
- **Input**: User provides codebase name and vector search result count
- **Validation**: Form validates required fields before processing
- **Trigger**: Submit button initiates the `generate_spec()` function

### 2. Three Parallel Processing Branches

#### A. Server Information Extraction
1. Vector search on external files for server-related content
2. LLM analysis to extract host, port, and database information
3. Validation of server information through additional LLM calls

#### B. Database Information Processing
1. **Dual Vector Search**: Internal codebase + external files
2. **File-by-File Analysis**: 
   - SQL detection using LLM
   - Query extraction and validation
   - Table/column information extraction
   - HTML table parsing for structured data
3. **Categorization**: Valid queries vs invalid queries

#### C. Address Extraction
- Calls `get_addresses()` function (currently not implemented)
- Extracts addresses and dependent addresses from codebase

### 3. Backend Services Architecture

#### Vector Search Service (Port 5000)
- **Endpoint**: `/vector-search`
- **Function**: Similarity search using PGVector database
- **Input**: Codebase name, query, result count
- **Output**: Relevant code snippets with metadata

#### LLM Processing Service (Port 8082)
- **Endpoint**: `/LLM-API`
- **Function**: LLM analysis using llama-3 model
- **Input**: System prompt, user prompt, code snippet
- **Output**: Processed analysis results

### 4. Data Flow Pattern
Each processing branch follows this pattern:
1. **Vector Search** → Retrieve relevant code snippets
2. **LLM Analysis** → Extract specific information
3. **Validation** → Verify extracted data quality
4. **Aggregation** → Compile into structured JSON

### 5. Final Output
- **JSON Compilation**: All extracted data combined into single document
- **Display**: Results shown in Streamlit interface
- **Persistence**: JSON pushed to GitHub repository

## Key Components

- **Frontend**: Streamlit web interface (`2_Spec_Generation.py`)
- **Vector Search**: PGVector-based similarity search
- **LLM Processing**: LangChain + llama-3 model integration
- **Data Storage**: GitHub repository for final specifications
- **Output Format**: Structured JSON with server, database, and address information
# Dynamic Specification Generation

## Overview

The Dynamic Specification Generation system is an enhanced version of the original LLMUtil that adapts to different codebases automatically. It provides robust error handling, language-specific analysis, and intelligent fallback mechanisms.

## Key Improvements

### 🎯 Adaptive Analysis
- **Language Detection**: Automatically detects programming languages and frameworks
- **Dynamic Prompting**: Creates context-aware prompts based on detected technology stack
- **Pattern Pre-filtering**: Uses regex patterns to pre-screen content before expensive LLM calls

### 🛡️ Robust Error Handling  
- **Retry Mechanisms**: Automatic retry with exponential backoff
- **Timeout Management**: Configurable request timeouts
- **Graceful Degradation**: Continues processing even when individual files fail

### 🔧 Multi-Strategy JSON Parsing
- **Direct Parsing**: Standard JSON parsing
- **Code Block Extraction**: Extracts JSON from markdown code blocks
- **Pattern Matching**: Finds JSON-like structures in free text

### 📊 Enhanced User Experience
- **Progress Indicators**: Real-time progress with Streamlit spinners
- **Error Reporting**: Detailed error messages with context
- **Result Statistics**: Summary of analysis results
- **Expandable Views**: Collapsible sections for detailed data

## Architecture

### Core Components

#### 1. CodebaseAnalyzer
- Detects programming languages from file extensions and content
- Maintains language-specific patterns for SQL and server detection
- Provides pre-filtering to reduce unnecessary LLM calls

#### 2. DynamicLLMProcessor  
- Handles all LLM interactions with retry logic
- Implements multiple JSON extraction strategies
- Creates adaptive prompts based on codebase context

#### 3. Profile-Based Configuration
- JSON configuration file with pre-defined codebase profiles
- Customizable patterns for different technology stacks
- Validation rules and fallback strategies

### Supported Languages & Frameworks

| Language/Framework | File Types | Specialized Patterns |
|-------------------|------------|---------------------|
| Java Spring | `.java`, `.properties`, `.yml`, `.xml` | JPA queries, Spring annotations, configuration |
| Python Django | `.py`, `.html`, `.txt` | Django ORM, settings, models |
| Node.js Express | `.js`, `.ts`, `.json`, `.env` | Sequelize, MongoDB, Express routes |
| .NET Core | `.cs`, `.json`, `.config` | Entity Framework, Kestrel, SQL Server |
| Microservices | `.yml`, `.yaml`, `.json`, `.xml` | Service discovery, API gateways |
| Cloud Native | `.yml`, `.yaml`, `.tf`, `.json` | AWS, Azure, GCP patterns |

## Usage

### Basic Usage

1. **Start the Application**
   ```bash
   cd genai-pilot-ui
   streamlit run pages/2_Spec_Generation_Dynamic.py
   ```

2. **Configure Analysis**
   - Enter your codebase name
   - Set vector search result count (default: 10)
   - Click "Generate Specification"

3. **Review Results**
   - Server Information: Extracted connection details
   - Database Information: Tables, columns, SQL queries
   - Addresses: Internal and external endpoints
   - Summary: Statistics and downloadable JSON

### Advanced Configuration

#### Custom Codebase Profiles

Edit `config/codebase_profiles.json` to add custom patterns:

```json
{
  "profiles": {
    "my_custom_stack": {
      "name": "My Custom Stack",
      "patterns": {
        "sql": ["custom_query_pattern"],
        "server": ["custom_server_pattern"]
      },
      "file_types": [".custom"],
      "keywords": ["custom_keyword"]
    }
  }
}
```

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_BACKEND_URL` | LLM service endpoint | `http://localhost:8082` |
| `VECTOR_SEARCH_URL` | Vector search endpoint | `https://localhost:5000` |
| `MAX_RETRIES` | Maximum retry attempts | `3` |
| `REQUEST_TIMEOUT` | Request timeout (seconds) | `30` |

## Error Handling

### Common Issues & Solutions

#### 1. LLM Request Failures
**Symptoms**: "Request failed" messages
**Solutions**: 
- Check backend service availability
- Verify network connectivity
- Increase retry count or timeout

#### 2. JSON Parsing Errors
**Symptoms**: "Could not extract valid data" warnings
**Solutions**:
- Review LLM response format
- Check if custom patterns are needed
- Use manual validation mode

#### 3. Empty Results
**Symptoms**: No data extracted from codebase
**Solutions**:
- Verify codebase name exists in vector store
- Check file content is substantive (>10 characters)
- Try increasing vector search result count

### Debug Mode

Enable debug logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

### Best Practices

1. **Vector Search Tuning**
   - Start with 10 results, increase if needed
   - Use specific search queries for targeted analysis
   - Consider codebase size when setting limits

2. **Content Pre-filtering**
   - Leverage pattern matching before LLM calls
   - Skip files with minimal content (<10 chars)
   - Use language-specific heuristics

3. **Batch Processing**
   - Process similar files together
   - Cache common pattern matches
   - Implement progressive result display

### Resource Usage

| Component | Memory Usage | CPU Usage | Network |
|-----------|-------------|-----------|---------|
| Language Detection | Low | Low | None |
| Pattern Matching | Low | Medium | None |  
| Vector Search | Medium | Low | High |
| LLM Processing | Medium | Medium | High |

## Integration

### API Endpoints

The system integrates with existing endpoints:

- **Vector Search**: `POST /vector-search`
- **LLM Processing**: `POST /LLM-API`  
- **GitHub Storage**: `POST /github-commit`

### Data Flow

```mermaid
graph LR
    A[User Input] --> B[Language Detection]
    B --> C[Pattern Pre-filtering]  
    C --> D[Vector Search]
    D --> E[LLM Analysis]
    E --> F[JSON Extraction]
    F --> G[Validation]
    G --> H[Result Compilation]
    H --> I[GitHub Storage]
```

## Migration Guide

### From Original LLMUtil

1. **Update Imports**
   ```python
   # Old
   from utils.LLMUtil import SQL_DB_Extraction_v2, Server_LLM_Extraction
   
   # New  
   from utils.DynamicLLMUtil import dynamic_sql_extraction, dynamic_server_extraction
   ```

2. **Update Function Calls**
   ```python
   # Old
   tables, queries, invalid = SQL_DB_Extraction_v2(data, prompt)
   
   # New
   tables, queries, invalid = dynamic_sql_extraction(data, prompt)
   ```

3. **Use New Page**
   ```bash
   # Access the new dynamic version
   streamlit run pages/2_Spec_Generation_Dynamic.py
   ```

### Backward Compatibility

The original LLMUtil functions remain available for backward compatibility. However, new projects should use the dynamic version for improved reliability and features.

## Troubleshooting

### Validation Checklist

- [ ] Backend services are running (ports 5000, 8082)
- [ ] Codebase exists in vector store
- [ ] Network connectivity to services
- [ ] Sufficient disk space for temporary files
- [ ] Valid configuration files in place

### Log Analysis

Check logs for common patterns:

```bash
# Successful processing
"Successfully identified SQL interaction"
"Valid server information found"

# Warning conditions  
"No SQL patterns detected, skipping"
"Content too short, skipping"

# Error conditions
"Request timed out"
"Could not extract valid data"
"Failed after N attempts"
```

### Support

For issues not covered in this guide:

1. Check the application logs for detailed error messages
2. Verify all backend services are operational
3. Test with a simple, known codebase first
4. Review the configuration files for syntax errors

## Future Enhancements

- [ ] Machine learning-based pattern recognition
- [ ] Custom validation rules per codebase
- [ ] Real-time collaboration features
- [ ] Advanced caching mechanisms
- [ ] Integration with CI/CD pipelines
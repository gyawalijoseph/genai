"""
Dynamic Specification Generation Frontend
Works with ANY codebase - no dependency on LLM response parsing
"""
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8082"
SPEC_ENDPOINT = f"{API_BASE_URL}/generate-spec"
COMPONENT_ENDPOINT = f"{API_BASE_URL}/extract-component"
VALIDATE_ENDPOINT = f"{API_BASE_URL}/validate-codebase"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"

class SpecGenerationClient:
    """Client for interacting with the specification generation API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 60
    
    def check_health(self) -> bool:
        """Check if the backend service is healthy"""
        try:
            response = self.session.get(HEALTH_ENDPOINT)
            return response.status_code == 200
        except:
            return False
    
    def validate_codebase(self, codebase: str) -> Dict[str, Any]:
        """Validate if codebase exists in vector store"""
        try:
            response = self.session.post(VALIDATE_ENDPOINT, json={"codebase": codebase})
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "message": "Validation failed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def generate_full_spec(self, codebase: str, max_results: int = 20) -> Dict[str, Any]:
        """Generate complete specification for codebase"""
        try:
            payload = {
                "codebase": codebase,
                "max_results": max_results,
                "include_summary": True
            }
            
            response = self.session.post(SPEC_ENDPOINT, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.content else {}
                return {
                    "status": "error", 
                    "message": error_data.get("message", f"HTTP {response.status_code}")
                }
                
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Request timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def extract_component(self, codebase: str, component: str, max_results: int = 10) -> Dict[str, Any]:
        """Extract specific component"""
        try:
            payload = {
                "codebase": codebase,
                "component": component,
                "max_results": max_results
            }
            
            response = self.session.post(COMPONENT_ENDPOINT, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.content else {}
                return {
                    "status": "error",
                    "message": error_data.get("message", f"HTTP {response.status_code}")
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

def render_header():
    """Render page header"""
    st.set_page_config(
        page_title="Dynamic Spec Generation",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🚀 Dynamic Specification Generation")
    st.markdown("""
    **Universal codebase analyzer** - Works with ANY programming language or framework.
    No manual configuration required. Powered by LangChain and intelligent fallbacks.
    """)

def render_sidebar() -> Dict[str, Any]:
    """Render sidebar with configuration options"""
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Codebase input
        codebase = st.text_input(
            "Codebase Name",
            placeholder="my-spring-app",
            help="Enter the name of your codebase as stored in the vector database"
        )
        
        # Advanced options
        with st.expander("🔧 Advanced Options", expanded=False):
            max_results = st.slider(
                "Max Search Results",
                min_value=10,
                max_value=100,
                value=20,
                help="Maximum number of code snippets to analyze"
            )
            
            extract_mode = st.selectbox(
                "Extraction Mode",
                ["Full Analysis", "Component Only"],
                help="Choose between complete analysis or specific component extraction"
            )
            
            if extract_mode == "Component Only":
                component = st.selectbox(
                    "Component",
                    ["sql", "server", "api", "dependencies"],
                    help="Select specific component to extract"
                )
            else:
                component = None
        
        # Service status
        st.markdown("---")
        st.subheader("🏥 Service Status")
        
        client = SpecGenerationClient()
        if client.check_health():
            st.success("✅ Backend service is healthy")
        else:
            st.error("❌ Backend service unavailable")
            st.warning("Make sure the Flask service is running on port 8082")
        
        return {
            "codebase": codebase,
            "max_results": max_results,
            "extract_mode": extract_mode,
            "component": component
        }

def render_codebase_validation(client: SpecGenerationClient, codebase: str):
    """Render codebase validation section"""
    
    if not codebase:
        st.info("👈 Enter a codebase name to begin analysis")
        return False
    
    # Validate codebase
    with st.spinner(f"Validating codebase '{codebase}'..."):
        validation = client.validate_codebase(codebase)
    
    if validation.get("status") == "error":
        st.error(f"❌ Validation failed: {validation.get('message')}")
        return False
    
    exists = validation.get("exists", False)
    if exists:
        st.success(f"✅ Codebase '{codebase}' found in vector store")
        return True
    else:
        st.warning(f"⚠️ Codebase '{codebase}' not found in vector store")
        st.info("Make sure you've generated embeddings for this codebase first")
        return False

def render_progress_tracking():
    """Render progress tracking components"""
    
    # Progress containers
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Progress steps
    steps = [
        "🔍 Retrieving code documents",
        "🧠 Analyzing with LangChain", 
        "🗄️ Extracting database info",
        "🖥️ Finding server configurations",
        "🌐 Discovering API endpoints",
        "📦 Identifying dependencies",
        "📊 Compiling results"
    ]
    
    return progress_bar, status_text, steps

def simulate_progress(progress_bar, status_text, steps):
    """Simulate progress updates (since we don't have real-time updates from backend)"""
    
    for i, step in enumerate(steps):
        progress = (i + 1) / len(steps)
        progress_bar.progress(progress)
        status_text.text(step)
        time.sleep(0.5)  # Small delay for UX
    
    status_text.text("✅ Analysis complete!")

def render_summary_metrics(summary: Dict[str, Any]):
    """Render summary metrics with visualizations"""
    
    st.subheader("📊 Analysis Summary")
    
    stats = summary.get("statistics", {})
    coverage = summary.get("coverage", {})
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Database Queries",
            stats.get("database_queries", 0),
            help="SQL queries and database operations found"
        )
    
    with col2:
        st.metric(
            "API Endpoints", 
            stats.get("api_endpoints", 0),
            help="REST endpoints and routes discovered"
        )
    
    with col3:
        st.metric(
            "Dependencies",
            stats.get("dependencies", 0),
            help="External libraries and frameworks"
        )
    
    with col4:
        st.metric(
            "Coverage",
            f"{coverage.get('percentage', 0):.0f}%",
            help="Percentage of specification areas covered"
        )
    
    # Coverage visualization
    if coverage:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = coverage.get('percentage', 0),
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Analysis Coverage"},
            delta = {'reference': 80},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"},
                    {'range': [80, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

def render_detailed_results(data: Dict[str, Any]):
    """Render detailed analysis results"""
    
    # Server Information
    st.subheader("🖥️ Server Information")
    server_info = data.get("server_information", [])
    
    if server_info:
        for i, server in enumerate(server_info):
            with st.expander(f"Server Configuration {i+1}", expanded=i==0):
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Hosts:**")
                    hosts = server.get("hosts", [])
                    if hosts:
                        for host in hosts:
                            st.code(host, language="text")
                    else:
                        st.info("No hosts found")
                
                with col2:
                    st.write("**Ports:**")
                    ports = server.get("ports", [])
                    if ports:
                        for port in ports:
                            st.code(port, language="text")
                    else:
                        st.info("No ports found")
                
                st.write("**Endpoints:**")
                endpoints = server.get("endpoints", [])
                if endpoints:
                    for endpoint in endpoints:
                        st.code(endpoint, language="text")
                else:
                    st.info("No endpoints found")
    else:
        st.info("No server information found")
    
    # Database Information
    st.subheader("🗄️ Database Information")
    db_info = data.get("database_information", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**SQL Queries:**")
        queries = db_info.get("queries", [])
        if queries:
            for i, query in enumerate(queries[:10]):  # Show first 10
                with st.expander(f"Query {i+1}"):
                    st.code(query, language="sql")
            
            if len(queries) > 10:
                st.info(f"Showing 10 of {len(queries)} queries")
        else:
            st.info("No SQL queries found")
    
    with col2:
        st.write("**Database Tables:**")
        tables = db_info.get("tables", [])
        if tables:
            for table in tables:
                st.code(table, language="text")
        else:
            st.info("No database tables found")
    
    # API Endpoints
    st.subheader("🌐 API Endpoints")
    api_endpoints = data.get("api_endpoints", [])
    
    if api_endpoints:
        # Group endpoints by method if possible
        endpoint_df = pd.DataFrame({"Endpoint": api_endpoints})
        st.dataframe(endpoint_df, use_container_width=True)
    else:
        st.info("No API endpoints found")
    
    # Dependencies
    st.subheader("📦 Dependencies")
    dependencies = data.get("dependencies", [])
    
    if dependencies:
        # Create a simple visualization
        dep_counts = {}
        for dep in dependencies:
            # Try to categorize dependencies
            if any(keyword in dep.lower() for keyword in ['spring', 'boot']):
                category = 'Spring Framework'
            elif any(keyword in dep.lower() for keyword in ['database', 'sql', 'jdbc']):
                category = 'Database'
            elif any(keyword in dep.lower() for keyword in ['web', 'http', 'rest']):
                category = 'Web Framework'
            else:
                category = 'Other'
            
            dep_counts[category] = dep_counts.get(category, 0) + 1
        
        if dep_counts:
            fig = px.pie(
                values=list(dep_counts.values()),
                names=list(dep_counts.keys()),
                title="Dependency Categories"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Show all dependencies
        with st.expander("All Dependencies", expanded=False):
            for dep in dependencies:
                st.code(dep, language="text")
    else:
        st.info("No dependencies found")

def render_export_options(data: Dict[str, Any], codebase: str):
    """Render export and save options"""
    
    st.subheader("💾 Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Download JSON", use_container_width=True):
            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="💾 Save JSON File",
                data=json_str,
                file_name=f"{codebase}_specification.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📊 Download CSV", use_container_width=True):
            # Create CSV with flattened data
            rows = []
            
            # Add server info
            for server in data.get("server_information", []):
                rows.append({
                    "type": "server",
                    "item": str(server)
                })
            
            # Add database info
            for query in data.get("database_information", {}).get("queries", []):
                rows.append({
                    "type": "sql_query",
                    "item": query
                })
            
            # Add endpoints
            for endpoint in data.get("api_endpoints", []):
                rows.append({
                    "type": "api_endpoint", 
                    "item": endpoint
                })
            
            if rows:
                df = pd.DataFrame(rows)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Save CSV File",
                    data=csv,
                    file_name=f"{codebase}_specification.csv",
                    mime="text/csv"
                )
    
    with col3:
        if st.button("🐙 Save to GitHub", use_container_width=True):
            st.info("GitHub integration coming soon!")

def main():
    """Main application"""
    
    render_header()
    
    # Get configuration from sidebar
    config = render_sidebar()
    codebase = config["codebase"]
    
    # Initialize client
    client = SpecGenerationClient()
    
    # Main content area
    if not codebase:
        # Show welcome message and instructions
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### 🎯 How it Works
            
            1. **Enter your codebase name** in the sidebar
            2. **Validate** that embeddings exist for your codebase  
            3. **Choose analysis mode** - full analysis or specific components
            4. **Generate specification** with one click
            5. **Export results** in multiple formats
            
            ### ✨ Key Features
            
            - **Universal Support**: Works with any programming language
            - **Intelligent Extraction**: Uses LangChain tools with regex fallbacks
            - **Parallel Processing**: Fast analysis using concurrent extraction
            - **No Response Parsing**: Robust pipeline that always produces results
            - **Rich Visualizations**: Interactive charts and metrics
            """)
        
        with col2:
            st.info("""
            ### 📋 Supported Components
            
            - 🗄️ **Database**: SQL queries, tables, connections
            - 🖥️ **Server**: Hosts, ports, configurations  
            - 🌐 **API**: REST endpoints, routes
            - 📦 **Dependencies**: Libraries, frameworks
            - ⚙️ **Configuration**: Environment settings
            """)
        
        return
    
    # Validate codebase
    st.markdown("---")
    if not render_codebase_validation(client, codebase):
        return
    
    # Analysis section
    st.markdown("---")
    st.subheader("🔍 Specification Analysis")
    
    # Generate button
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if config["extract_mode"] == "Full Analysis":
            generate_button = st.button(
                "🚀 Generate Full Specification",
                type="primary",
                use_container_width=True
            )
        else:
            generate_button = st.button(
                f"🔧 Extract {config['component'].upper()} Component",
                type="primary", 
                use_container_width=True
            )
    
    # Process generation
    if generate_button:
        # Progress tracking
        progress_bar, status_text, steps = render_progress_tracking()
        
        # Start analysis
        simulate_progress(progress_bar, status_text, steps)
        
        # Make API call
        with st.spinner("🧠 Processing with AI models..."):
            if config["extract_mode"] == "Full Analysis":
                result = client.generate_full_spec(codebase, config["max_results"])
            else:
                result = client.extract_component(codebase, config["component"], config["max_results"])
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Handle results
        if result.get("status") == "error":
            st.error(f"❌ Analysis failed: {result.get('message')}")
            return
        
        # Success! Show results
        st.success("✅ Analysis completed successfully!")
        
        # Show summary if available
        if "summary" in result:
            render_summary_metrics(result["summary"])
        
        # Show detailed results
        st.markdown("---")
        render_detailed_results(result.get("data", {}))
        
        # Export options
        st.markdown("---") 
        render_export_options(result.get("data", {}), codebase)
        
        # Raw data expander
        with st.expander("🔍 Raw API Response", expanded=False):
            st.json(result)

if __name__ == "__main__":
    main()
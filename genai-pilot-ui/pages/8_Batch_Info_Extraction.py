import streamlit as st
import json
import time
from datetime import datetime

from utils.githubUtil import commit_json
from utils.metadataUtil import fetch_metadata
from utils.extractionUtil import (
    vector_search_multiple,
    extract_server_information_batch,
    extract_database_information_batch,
    transform_extracted_data_batch
)

# Dynamic configuration - can be modified for any codebase
DEFAULT_DATABASE_SYSTEM_PROMPT = "You are an expert at analyzing code for database configurations, connections, queries, and data models."
DEFAULT_SERVER_SYSTEM_PROMPT = "You are an expert at analyzing code for server configurations, host information, and network settings."
DEFAULT_DATABASE_VECTOR_QUERY = "database sql connection query schema table model"
DEFAULT_SERVER_VECTOR_QUERY = "server host port configuration"

# Initialize session state for batch processing
if 'batch_results' not in st.session_state:
    st.session_state['batch_results'] = {}
if 'batch_progress' not in st.session_state:
    st.session_state['batch_progress'] = {}
if 'batch_status' not in st.session_state:
    st.session_state['batch_status'] = {}
if 'batch_running' not in st.session_state:
    st.session_state['batch_running'] = False


def process_single_codebase(codebase, config, progress_placeholder):
    """Process a single codebase and return results"""
    try:
        progress_placeholder.info(f"🔄 **{codebase}**: Starting...")
        
        # Initialize results structure
        combined_results = {
            "extraction_metadata": {
                "extraction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "codebase": codebase,
                "extraction_type": "batch_combined_extraction"
            },
            "Application": {},
            "Server Information": [],
            "Database Information": {
                "Table Information": [],
                "SQL_QUERIES": [],
                "Invalid_SQL_Queries": []
            }
        }
        
        # Step 0: Car Info (Application Metadata) Extraction
        progress_placeholder.info(f"🚗 **{codebase}**: Fetching Car Info...")
        try:
            metadata = fetch_metadata(codebase)
            if metadata is not None:
                combined_results['Application'] = metadata
                progress_placeholder.success(f"✅ **{codebase}**: Car Info extracted")
            else:
                combined_results['Application'] = {}
                progress_placeholder.warning(f"⚠️ **{codebase}**: No Car Info found")
        except Exception as e:
            progress_placeholder.error(f"❌ **{codebase}**: Car info failed - {str(e)}")
            combined_results['Application'] = {}
        
        # Search suffixes for both main and external files
        search_suffixes = ["-external-files", ""]
        
        # Step 1: Server Information Extraction
        progress_placeholder.info(f"🖥️ **{codebase}**: Extracting Server Info...")
        try:
            server_data = vector_search_multiple(
                codebase, 
                config['server_vector_query'], 
                config['vector_results_count'], 
                search_suffixes
            )
            
            if server_data and 'results' in server_data and len(server_data['results']) > 0:
                server_information = extract_server_information_batch(
                    server_data, 
                    config['server_system_prompt'], 
                    config['server_vector_query']
                )
                combined_results["Server Information"] = server_information
                progress_placeholder.success(f"✅ **{codebase}**: Found {len(server_information)} server entries")
            else:
                progress_placeholder.warning(f"⚠️ **{codebase}**: No server information found")
        except Exception as e:
            progress_placeholder.error(f"❌ **{codebase}**: Server extraction failed - {str(e)}")
        
        # Step 2: Database Information Extraction
        progress_placeholder.info(f"🗄️ **{codebase}**: Extracting Database Info...")
        try:
            database_data = vector_search_multiple(
                codebase, 
                config['database_vector_query'], 
                config['vector_results_count'], 
                search_suffixes
            )
            
            if database_data and 'results' in database_data and len(database_data['results']) > 0:
                database_information = extract_database_information_batch(
                    database_data, 
                    config['database_system_prompt'], 
                    config['database_vector_query']
                )
                
                # Transform database information using extracted data
                transformed_database_data = transform_extracted_data_batch(
                    database_information, 
                    database_data['results'], 
                    config['database_system_prompt']
                )
                combined_results["Database Information"] = transformed_database_data
                progress_placeholder.success(f"✅ **{codebase}**: Found {len(transformed_database_data.get('Table Information', []))} tables, {len(transformed_database_data.get('SQL_QUERIES', []))} queries")
            else:
                progress_placeholder.warning(f"⚠️ **{codebase}**: No database information found")
        except Exception as e:
            progress_placeholder.error(f"❌ **{codebase}**: Database extraction failed - {str(e)}")
        
        # Step 3: Commit to GitHub
        progress_placeholder.info(f"📤 **{codebase}**: Committing to GitHub...")
        try:
            commit_result = commit_json(codebase, combined_results)
            progress_placeholder.success(f"✅ **{codebase}**: Completed - {commit_result}")
        except Exception as e:
            progress_placeholder.error(f"❌ **{codebase}**: GitHub commit failed - {str(e)}")
        
        return combined_results, None
        
    except Exception as e:
        progress_placeholder.error(f"❌ **{codebase}**: Critical error - {str(e)}")
        return None, str(e)


def run_batch_processing_sequential(codebases, config):
    """Run batch processing for multiple codebases sequentially"""
    st.session_state['batch_running'] = True
    st.session_state['batch_results'] = {}
    
    # Create progress container
    progress_container = st.container()
    progress_placeholder = progress_container.empty()
    
    # Process each codebase sequentially
    for i, codebase in enumerate(codebases, 1):
        progress_placeholder.info(f"🚀 **Processing {i}/{len(codebases)}**: {codebase}")
        
        # Process single codebase
        results, error = process_single_codebase(codebase, config, progress_placeholder)
        
        if error:
            st.session_state['batch_results'][codebase] = None
            progress_placeholder.error(f"❌ **{codebase}**: Failed - {error}")
        else:
            st.session_state['batch_results'][codebase] = results
            progress_placeholder.success(f"✅ **{codebase}**: Successfully completed!")
        
        # Small delay to show progress
        time.sleep(0.5)
    
    st.session_state['batch_running'] = False
    progress_placeholder.success(f"🎉 **Batch processing completed!** Processed {len(codebases)} codebases.")
    return st.session_state['batch_results']


def display_batch_status():
    """Display simple batch status for sequential processing"""
    if st.session_state.get('batch_running', False):
        st.info("🔄 **Batch processing is currently running...**")
    elif st.session_state['batch_results']:
        completed_count = sum(1 for r in st.session_state['batch_results'].values() if r is not None)
        total_count = len(st.session_state['batch_results'])
        st.success(f"✅ **Batch processing completed:** {completed_count}/{total_count} codebases processed successfully")
    else:
        st.info("⏸️ **No batch processing currently active**")


def display_batch_results():
    """Display results from completed batch processing"""
    if not st.session_state['batch_results']:
        return
    
    st.subheader("📋 Batch Processing Results")
    
    completed_count = sum(1 for r in st.session_state['batch_results'].values() if r is not None)
    total_count = len(st.session_state['batch_progress'])
    
    st.info(f"**Completed:** {completed_count}/{total_count} codebases")
    
    # Display results for each completed codebase
    for codebase, results in st.session_state['batch_results'].items():
        if results is not None:
            with st.expander(f"📊 Results for: {codebase}", expanded=False):
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    app_info_count = 1 if results.get('Application') else 0
                    st.metric("Application Info", app_info_count)
                
                with col2:
                    server_count = len(results.get('Server Information', []))
                    st.metric("Server Info", server_count)
                
                with col3:
                    db_tables = len(results.get('Database Information', {}).get('Table Information', []))
                    st.metric("DB Tables", db_tables)
                
                # Full JSON results
                st.json(results)
                
                # Download option
                results_json = json.dumps(results, indent=2)
                st.download_button(
                    label=f"📥 Download {codebase} Results",
                    data=results_json,
                    file_name=f"batch_extraction_{codebase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key=f"download_{codebase}"
                )


def main():
    st.set_page_config(
        page_title="Batch Information Extraction",
        page_icon="🚀",
        layout="wide"
    )

    st.title("🚀 Batch Information Extraction")
    st.markdown("**Process multiple codebases simultaneously with background processing**")

    # Configuration section
    st.header("⚙️ Batch Configuration")
    
    with st.form("batch_config_form"):
        col1, col2 = st.columns(2)

        with col1:
            codebases_input = st.text_input(
                "📝 Codebases (comma-separated):",
                placeholder="codebase1, codebase2, codebase3",
                help="Enter codebase names separated by commas"
            )

            database_system_prompt = st.text_area(
                "🗄️ Database System Prompt:",
                value=DEFAULT_DATABASE_SYSTEM_PROMPT,
                height=100,
                help="Instructions for database extraction"
            )

            database_vector_query = st.text_input(
                "🔍 Database Vector Query:",
                value=DEFAULT_DATABASE_VECTOR_QUERY,
                help="Query used to find database-related files"
            )

        with col2:
            vector_results_count = st.number_input(
                '📊 Max Results Count (per database):',
                value=10,
                min_value=1,
                max_value=50,
                help="Maximum number of files to process from each vector database"
            )
            
            server_system_prompt = st.text_area(
                "🖥️ Server System Prompt:",
                value=DEFAULT_SERVER_SYSTEM_PROMPT,
                height=100,
                help="Instructions for server extraction"
            )

            server_vector_query = st.text_input(
                "🔍 Server Vector Query:",
                value=DEFAULT_SERVER_VECTOR_QUERY,
                help="Query used to find server-related files"
            )

        st.info("🔄 **Processing Mode:** Sequential (one codebase at a time)")

        start_batch_button = st.form_submit_button(
            '🚀 Start Batch Processing',
            use_container_width=True,
            disabled=st.session_state.get('batch_running', False)
        )

    # Process form submission
    if start_batch_button:
        if not codebases_input.strip():
            st.error("❌ Please enter at least one codebase")
        else:
            # Parse codebases (comma-separated)
            codebases = [codebase.strip() for codebase in codebases_input.split(',') if codebase.strip()]
            
            if len(codebases) == 0:
                st.error("❌ No valid codebases found")
            else:
                st.info(f"🎯 **Starting batch processing for {len(codebases)} codebases:**")
                for codebase in codebases:
                    st.write(f"• {codebase}")
                
                # Create configuration object
                config = {
                    'database_system_prompt': database_system_prompt,
                    'server_system_prompt': server_system_prompt,
                    'database_vector_query': database_vector_query,
                    'server_vector_query': server_vector_query,
                    'vector_results_count': vector_results_count
                }
                
                # Start sequential batch processing
                with st.spinner("Processing codebases..."):
                    results = run_batch_processing_sequential(codebases, config)
                
                st.success("✅ **Batch processing completed!**")
                st.balloons()

    # Control section
    st.header("🎛️ Batch Control")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state['batch_results'] = {}
            st.success("Results cleared!")
            st.rerun()
    
    with col2:
        running_status = "🟢 Running" if st.session_state.get('batch_running', False) else "🔴 Idle"
        st.info(f"**Status:** {running_status}")

    # Display status and results
    st.markdown("---")
    
    display_batch_status()
    display_batch_results()

    # Summary section
    if st.session_state['batch_results']:
        st.header("📊 Batch Summary")
        
        all_results = {
            "batch_metadata": {
                "batch_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_codebases": len(st.session_state['batch_progress']),
                "completed_codebases": len([r for r in st.session_state['batch_results'].values() if r is not None]),
                "batch_type": "multi_codebase_extraction"
            },
            "results": st.session_state['batch_results']
        }
        
        # Download all results
        all_results_json = json.dumps(all_results, indent=2)
        st.download_button(
            label="📥 Download All Batch Results",
            data=all_results_json,
            file_name=f"batch_all_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )


if __name__ == "__main__":
    main()
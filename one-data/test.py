import json
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

class MermaidERGenerator:
    def __init__(self, application_id: str = "500000383"):
        self.application_id = application_id
    
    def generate_complete_diagram(self, json_data: str) -> str:
        """Generate complete ER diagram with all databases"""
        data = json.loads(json_data)
        databases = self._parse_databases(data.get('databases', []))
        
        lines = [
            "erDiagram",
            f"    APPLICATION_{self.application_id} {{",
            f'        string application_id "{self.application_id}"',
            "    }",
            ""
        ]
        
        # Generate database entities
        for db in databases:
            lines.extend(self._generate_database_section(db))
        
        # Generate relationships
        lines.extend(self._generate_relationships(databases))
        
        return "\n".join(lines)
    
    def generate_individual_diagram(self, json_data: str, database_name: str) -> str:
        """Generate diagram for a specific database"""
        data = json.loads(json_data)
        databases = self._parse_databases(data.get('databases', []))
        
        target_db = next((db for db in databases if db['name'] == database_name), None)
        if not target_db:
            raise ValueError(f"Database '{database_name}' not found")
        
        root_id = self._sanitize_id(database_name) + "_ROOT"
        
        lines = [
            "erDiagram",
            f"    {root_id} {{",
            f'        string database_name "{database_name}"',
            f'        string database_type "{target_db.get("type", "unknown")}"',
            "    }",
            ""
        ]
        
        # Generate tables and columns
        table_ids = []
        for entity in target_db.get('entities', []):
            table_id = self._generate_table_section(lines, entity)
            table_ids.append(table_id)
        
        # Generate relationships for individual database
        lines.append("    %% Relationships")
        for entity in target_db.get('entities', []):
            table_id = self._sanitize_id(entity['table_name']) + "_TABLE"
            columns_id = self._sanitize_id(entity['table_name']) + "_COLUMNS"
            
            lines.append(f"    {root_id} ||--o{{ {table_id} : contains")
            lines.append(f"    {table_id} ||--o{{ {columns_id} : has_columns")
        
        return "\n".join(lines)
    
    def _parse_databases(self, databases_json: List[Dict]) -> List[Dict]:
        """Parse and filter databases from JSON"""
        databases = []
        for db in databases_json:
            db_name = db.get('databaseName', '').strip()
            if db_name and db_name != 'unknown':
                databases.append({
                    'name': db_name,
                    'type': db.get('databaseType', 'unknown'),
                    'bucket': db.get('bucketName', ''),
                    'cluster': db.get('clusterName', ''),
                    'schema': db.get('schemaName', ''),
                    'entities': db.get('entities', [])
                })
        return databases
    
    def _generate_database_section(self, db: Dict) -> List[str]:
        """Generate database entity and its tables"""
        lines = []
        db_id = self._sanitize_id(db['name']) + "_DB"
        
        # Database entity
        lines.extend([
            f"    %% {db['name']} Database",
            f"    {db_id} {{",
            f'        string database_name "{db["name"]}"',
            f'        string database_type "{db["type"]}"',
            "    }",
            ""
        ])
        
        # Table entities - ensure all tables are captured
        for entity in db['entities']:
            self._generate_table_section(lines, entity)
        
        return lines
    
    def _generate_table_section(self, lines: List[str], entity: Dict) -> str:
        """Generate table and columns entities"""
        table_name = entity.get('table_name', 'unknown_table')
        table_id = self._sanitize_id(table_name) + "_TABLE"
        columns_id = self._sanitize_id(table_name) + "_COLUMNS"
        
        # Table entity
        lines.extend([
            f"    {table_id} {{",
            f'        string table_name "{table_name}"',
            "    }",
            ""
        ])
        
        # Columns entity
        columns = entity.get('columns', [])
        lines.append(f"    {columns_id} {{")
        
        if columns:
            for col in columns:
                col_line = self._format_column(col)
                lines.append(f"        {col_line}")
        else:
            lines.append('        string status "No columns defined"')
        
        lines.extend(["    }", ""])
        
        return table_id
    
    def _format_column(self, column: Dict) -> str:
        """Format column for Mermaid entity"""
        col_name = column.get('column_name', 'unknown_column')
        crud = column.get('CRUD', 'unknown')
        datatype = column.get('datatype', 'unknown')
        
        sanitized_name = self._sanitize_column_name(col_name)
        description = f"{crud}|{datatype}"
        
        return f'{datatype} {sanitized_name} "{description}"'
    
    def _generate_relationships(self, databases: List[Dict]) -> List[str]:
        """Generate all relationships"""
        lines = ["    %% Relationships"]
        
        # Application to Database relationships
        for db in databases:
            db_id = self._sanitize_id(db['name']) + "_DB"
            lines.append(f"    APPLICATION_{self.application_id} ||--o{{ {db_id} : contains")
        lines.append("")
        
        # Database to Table relationships
        lines.append("    %% Database to Table relationships")
        for db in databases:
            db_id = self._sanitize_id(db['name']) + "_DB"
            for entity in db['entities']:
                table_id = self._sanitize_id(entity['table_name']) + "_TABLE"
                lines.append(f"    {db_id} ||--o{{ {table_id} : has")
        lines.append("")
        
        # Table to Column relationships
        lines.append("    %% Table to Column relationships")
        for db in databases:
            for entity in db['entities']:
                table_id = self._sanitize_id(entity['table_name']) + "_TABLE"
                columns_id = self._sanitize_id(entity['table_name']) + "_COLUMNS"
                lines.append(f"    {table_id} ||--o{{ {columns_id} : contains")
        
        return lines
    
    def _sanitize_id(self, text: str) -> str:
        """Sanitize text for Mermaid entity ID"""
        if not text:
            return "UNKNOWN"
        return re.sub(r'[^A-Z0-9_]', '_', text.upper()).strip('_')
    
    def _sanitize_column_name(self, text: str) -> str:
        """Sanitize column name"""
        if not text:
            return "unknown_column"
        return re.sub(r'[^a-z0-9_.]', '_', text.lower()).strip('_')

def process_local_spec(spec_path: str, output_dir: str = None) -> Dict[str, str]:
    """
    Process local spec.json file and generate all diagrams
    
    Args:
        spec_path: Path to the spec.json file
        output_dir: Directory to save output files (default: same as input file)
    
    Returns:
        Dictionary with generated file paths
    """
    # Validate input file
    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    
    if not spec_file.suffix.lower() == '.json':
        raise ValueError(f"Input file must be a JSON file, got: {spec_file.suffix}")
    
    # Set output directory
    if output_dir is None:
        output_dir = spec_file.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read JSON file
    try:
        with open(spec_file, 'r', encoding='utf-8') as f:
            json_data = f.read()
    except Exception as e:
        raise IOError(f"Error reading spec file: {e}")
    
    # Initialize generator
    generator = MermaidERGenerator()
    
    # Generate complete diagram
    try:
        complete_diagram = generator.generate_complete_diagram(json_data)
        complete_output_path = output_dir / "complete_database_diagram.mmd"
        
        with open(complete_output_path, 'w', encoding='utf-8') as f:
            f.write(complete_diagram)
        
        print(f"✓ Complete diagram saved: {complete_output_path}")
        
    except Exception as e:
        raise RuntimeError(f"Error generating complete diagram: {e}")
    
    # Parse databases for individual diagrams
    try:
        data = json.loads(json_data)
        databases = generator._parse_databases(data.get('databases', []))
        
        individual_files = {}
        
        for db in databases:
            db_name = db['name']
            try:
                individual_diagram = generator.generate_individual_diagram(json_data, db_name)
                individual_output_path = output_dir / f"{db_name.lower()}_diagram.mmd"
                
                with open(individual_output_path, 'w', encoding='utf-8') as f:
                    f.write(individual_diagram)
                
                individual_files[db_name] = str(individual_output_path)
                print(f"✓ {db_name} diagram saved: {individual_output_path}")
                
            except Exception as e:
                print(f"⚠ Warning: Could not generate diagram for {db_name}: {e}")
                continue
        
        return {
            'complete_diagram': str(complete_output_path),
            'individual_diagrams': individual_files,
            'total_databases': len(databases),
            'successful_individual': len(individual_files)
        }
        
    except Exception as e:
        raise RuntimeError(f"Error processing individual diagrams: {e}")

def main():
    """Command line interface"""
    if len(sys.argv) < 2:
        print("Usage: python mermaid_generator.py <spec.json> [output_directory]")
        print("Example: python mermaid_generator.py ./spec1.json ./output/")
        sys.exit(1)
    
    spec_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print(f"Processing spec file: {spec_path}")
        results = process_local_spec(spec_path, output_dir)
        
        print(f"\n🎉 Success! Generated diagrams:")
        print(f"📊 Complete diagram: {results['complete_diagram']}")
        print(f"📈 Individual diagrams: {results['successful_individual']}/{results['total_databases']}")
        
        if results['individual_diagrams']:
            print("\nIndividual database diagrams:")
            for db_name, file_path in results['individual_diagrams'].items():
                print(f"  • {db_name}: {file_path}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

# Quick utility functions (keep for backwards compatibility)
def quick_generate_from_local_spec(spec_path: str):
    """Quick one-liner to process local spec file"""
    return process_local_spec(spec_path)

if __name__ == "__main__":
    main()
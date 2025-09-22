import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
import uuid

class DynamicMermaidERGenerator:
    def __init__(self, application_id: str = None):
        self.application_id = application_id
    
    def generate_complete_diagram(self, json_data: str) -> str:
        """Generate complete ER diagram with all valid databases"""
        data = json.loads(json_data)
        if self.application_id is None:
            app_info = data.get('application_information', {})
            self.application_id = app_info.get('application_id', '500000383')
        databases = self._parse_databases(data.get('databases', []))
        
        lines = [
            "erDiagram",
            f"    APPLICATION_{self.application_id} {{",
            "    }",
            ""
        ]
        
        # Generate database entities
        for db in databases:
            lines.extend(self._generate_database_section(db))
        
        # Generate relationships
        lines.extend(self._generate_relationships(databases))
        
        return "\n".join(lines)
    
    def generate_individual_diagram(self, db: Dict) -> str:
        """Generate ER diagram for a single database"""
        lines = [
            "erDiagram",
            f"    APPLICATION_{self.application_id} {{",
            "    }",
            ""
        ]
        
        # Generate database entity and its tables
        lines.extend(self._generate_database_section(db))
        
        # Generate relationships for this database only
        lines.extend(self._generate_individual_relationships(db))
        
        return "\n".join(lines)
    
    def _parse_databases(self, databases_json: List[Dict]) -> List[Dict]:
        """Parse and filter databases from JSON, skipping invalid or empty ones"""
        databases = []
        for db in databases_json:
            db_name = db.get('databaseName', '').strip()
            entities = db.get('entities', [])
            # Skip if database name is empty, 'unknown', or entities is empty
            if db_name and db_name.lower() != 'unknown' and entities:
                databases.append({
                    'name': db_name,
                    'type': db.get('databaseType', 'unknown'),
                    'bucket': db.get('bucketName', ''),
                    'cluster': db.get('clusterName', ''),
                    'schema': db.get('schemaName', ''),
                    'entities': entities,
                    'server_host': db.get('serverHost', ''),
                    'replica_set': db.get('replicaSet', '')
                })
        return databases
    
    def _generate_database_section(self, db: Dict) -> List[str]:
        """Generate database entity and its tables"""
        lines = []
        db_id = self._sanitize_id(db['name'])
        
        # Database entity
        lines.extend([
            f"    %% {db['name']} Database",
            f"    {db_id} {{",
        ])

        # Only add database_type if it's not "unknown"
        if db["type"] != "unknown":
            lines.append(f'        string database_type "{db["type"]}"')

        lines.extend([
            "    }",
            ""
        ])
        
        # Table entities - only create tables that have columns
        processed_tables = {}
        for idx, entity in enumerate(db['entities']):
            table_name = entity.get('table_name', f'unknown_table_{idx}')
            columns = entity.get('columns', [])

            # Only create table if it has columns
            if columns:
                # Handle duplicate table names by adding suffix
                unique_table_name = table_name
                counter = 1
                while unique_table_name in processed_tables:
                    unique_table_name = f"{table_name}_{counter}"
                    counter += 1

                processed_tables[unique_table_name] = entity
                self._generate_table_section(lines, entity, unique_table_name)
        
        return lines
    
    def _generate_table_section(self, lines: List[str], entity: Dict, table_name: str) -> str:
        """Generate table entity and separate columns entity"""
        table_id = self._sanitize_id(table_name)
        columns_id = self._sanitize_id(table_name) + "_columns"

        # Table entity - just the table name as header
        lines.extend([
            f"    {table_id} {{",
            "    }",
            ""
        ])

        # Columns entity - just column data, no header info
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
        """Format column for Mermaid entity with simplified CRUD notation"""
        col_name = column.get('column_name', 'unknown_column')
        crud = column.get('CRUD', 'unknown')
        datatype = column.get('datatype', 'unknown')
        
        sanitized_name = self._sanitize_column_name(col_name)
        
        # Convert CRUD operations to abbreviated form
        crud_abbrev = self._abbreviate_crud(crud)
        
        return f'{datatype} {sanitized_name} "{crud_abbrev}"'
    
    def _abbreviate_crud(self, crud: str) -> str:
        """Convert CRUD operations to abbreviated form"""
        if not crud or crud.lower() == 'unknown':
            return 'R'
        
        crud_lower = crud.lower()
        abbreviations = []
        
        # Check for each operation in CRUD order
        if 'create' in crud_lower or 'write' in crud_lower:
            abbreviations.append('C')
        if 'read' in crud_lower:
            abbreviations.append('R')
        if 'update' in crud_lower:
            abbreviations.append('U')
        if 'delete' in crud_lower:
            abbreviations.append('D')
        
        return ''.join(abbreviations) if abbreviations else 'R'
    
    def _generate_relationships(self, databases: List[Dict]) -> List[str]:
        """Generate all relationships for the complete diagram"""
        lines = ["    %% Relationships"]
        
        # Application to Database relationships
        for db in databases:
            db_id = self._sanitize_id(db['name'])
            lines.append(f"    APPLICATION_{self.application_id} ||--o{{ {db_id} : has")
        lines.append("")
        
        # Database to Table relationships (only for tables with columns)
        lines.append("    %% Database to Table relationships")
        for db in databases:
            db_id = self._sanitize_id(db['name'])
            processed_tables = {}

            for idx, entity in enumerate(db['entities']):
                table_name = entity.get('table_name', f'unknown_table_{idx}')
                columns = entity.get('columns', [])

                # Only create relationship if table has columns
                if columns:
                    # Handle duplicate table names
                    unique_table_name = table_name
                    counter = 1
                    while unique_table_name in processed_tables:
                        unique_table_name = f"{table_name}_{counter}"
                        counter += 1

                    processed_tables[unique_table_name] = True
                    table_id = self._sanitize_id(unique_table_name)
                    lines.append(f"    {db_id} ||--o{{ {table_id} : contains")
        lines.append("")

        # Table to Column relationships
        lines.append("    %% Table to Column relationships")
        for db in databases:
            processed_tables = {}

            for idx, entity in enumerate(db['entities']):
                table_name = entity.get('table_name', f'unknown_table_{idx}')
                columns = entity.get('columns', [])

                # Only create relationship if table has columns
                if columns:
                    # Handle duplicate table names
                    unique_table_name = table_name
                    counter = 1
                    while unique_table_name in processed_tables:
                        unique_table_name = f"{table_name}_{counter}"
                        counter += 1

                    processed_tables[unique_table_name] = True
                    table_id = self._sanitize_id(unique_table_name)
                    columns_id = self._sanitize_id(unique_table_name) + "_columns"
                    lines.append(f"    {table_id} ||--o{{ {columns_id} : contains")

        # Add styling for application entity
        lines.extend([
            "",
            f"    classDef appStyle fill:#e1f5fe,stroke:#01579b,stroke-width:3px",
            f"    class APPLICATION_{self.application_id} appStyle"
        ])

        return lines
    
    def _generate_individual_relationships(self, db: Dict) -> List[str]:
        """Generate relationships for a single database"""
        lines = ["    %% Relationships"]
        db_id = self._sanitize_id(db['name'])
        
        # Application to Database relationship
        lines.append(f"    APPLICATION_{self.application_id} ||--o{{ {db_id} : contains")
        lines.append("")
        
        # Database to Table relationships (only for tables with columns)
        lines.append("    %% Database to Table relationships")
        processed_tables = {}
        for idx, entity in enumerate(db['entities']):
            table_name = entity.get('table_name', f'unknown_table_{idx}')
            columns = entity.get('columns', [])

            # Only create relationship if table has columns
            if columns:
                # Handle duplicate table names
                unique_table_name = table_name
                counter = 1
                while unique_table_name in processed_tables:
                    unique_table_name = f"{table_name}_{counter}"
                    counter += 1

                processed_tables[unique_table_name] = True
                table_id = self._sanitize_id(unique_table_name)
                lines.append(f"    {db_id} ||--o{{ {table_id} : contains")
        lines.append("")

        # Table to Column relationships
        lines.append("    %% Table to Column relationships")
        processed_tables = {}
        for idx, entity in enumerate(db['entities']):
            table_name = entity.get('table_name', f'unknown_table_{idx}')
            columns = entity.get('columns', [])

            # Only create relationship if table has columns
            if columns:
                # Handle duplicate table names
                unique_table_name = table_name
                counter = 1
                while unique_table_name in processed_tables:
                    unique_table_name = f"{table_name}_{counter}"
                    counter += 1

                processed_tables[unique_table_name] = True
                table_id = self._sanitize_id(unique_table_name)
                columns_id = self._sanitize_id(unique_table_name) + "_columns"
                lines.append(f"    {table_id} ||--o{{ {columns_id} : contains")

        # Add styling for application entity
        lines.extend([
            "",
            f"    classDef appStyle fill:#e1f5fe,stroke:#01579b,stroke-width:3px",
            f"    class APPLICATION_{self.application_id} appStyle"
        ])

        return lines

    def _sanitize_id(self, text: str) -> str:
        """Sanitize text for Mermaid entity ID"""
        if not text:
            return "UNKNOWN"
        return re.sub(r'[^A-Z0-9.]', '_', text.upper()).replace('.', '_').strip('_')

    def _sanitize_column_name(self, text: str) -> str:
        """Sanitize column name"""
        if not text:
            return "unknown_column"
        return re.sub(r'[^a-z0-9.]', '_', text.lower()).replace('.', '_').strip('_')

def generate_mermaid_from_spec(spec_path: str, output_path: str = None, application_id: str = None) -> str:
    """
    Generate Mermaid ER diagram from JSON specification file and individual diagrams for each database

    Args:
        spec_path: Path to the JSON specification file
        output_path: Optional output file path for complete diagram (if None, prints to console)
        application_id: Application identifier for the root node

    Returns:
        Generated Mermaid diagram as string (complete diagram)
    """
    # Validate input file
    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(f"Specification file not found: {spec_path}")

    if not spec_file.suffix.lower() == '.json':
        raise ValueError(f"Input file must be a JSON file, got: {spec_file.suffix}")

    # Read JSON file
    try:
        with open(spec_file, 'r', encoding='utf-8') as f:
            json_data = f.read()
    except Exception as e:
        raise IOError(f"Error reading specification file: {e}")

    # Generate complete diagram
    generator = DynamicMermaidERGenerator(application_id)
    diagram = generator.generate_complete_diagram(json_data)

    # Parse databases for statistics and individual diagrams
    data = json.loads(json_data)
    databases = generator._parse_databases(data.get('databases', []))

    # Determine output directory
    output_dir = Path(output_path).parent if output_path else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)


    # Save or print complete diagram
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(diagram)
        print(f"Complete Mermaid diagram saved to: {output_path}")
    else:
        print(diagram)

    return diagram

def main():
    """Command line interface"""
    if len(sys.argv) < 2:
        print("Usage: python dynamic_mermaid_generator.py <spec.json> [output.mmd] [application_id]")
        print("Examples:")
        print("  python dynamic_mermaid_generator.py spec.json")
        print("  python dynamic_mermaid_generator.py spec.json diagram.mmd")
        print("  python dynamic_mermaid_generator.py spec.json diagram.mmd APP_12345")
        sys.exit(1)

    spec_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    application_id = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        print(f"Processing specification file: {spec_path}")
        if application_id:
            print(f"Using application ID: {application_id}")

        diagram = generate_mermaid_from_spec(spec_path, output_path, application_id)

        # Get statistics
        data = json.loads(Path(spec_path).read_text())
        databases = DynamicMermaidERGenerator(application_id)._parse_databases(data.get('databases', []))

        total_tables = sum(len(db.get('entities', [])) for db in databases)
        total_columns = sum(len(entity.get('columns', []))
                          for db in databases
                          for entity in db.get('entities', []))

        print(f"\nDiagram generated successfully!")
        print(f"Statistics:")
        print(f"  - Databases: {len(databases)}")
        print(f"  - Tables: {total_tables}")
        print(f"  - Columns: {total_columns}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def quick_generate(spec_file: str, app_id: str = None) -> str:
    """Quick one-liner to generate diagram"""
    return generate_mermaid_from_spec(spec_file, application_id=app_id)

if __name__ == "__main__":
    main()
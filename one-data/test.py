import json
import re
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

# Utility functions for easy usage
def generate_all_databases_diagram(json_file_path: str) -> str:
    """Generate complete diagram from JSON file"""
    with open(json_file_path, 'r') as f:
        json_data = f.read()
    
    generator = MermaidERGenerator()
    return generator.generate_complete_diagram(json_data)

def generate_database_diagram(json_file_path: str, database_name: str) -> str:
    """Generate individual database diagram from JSON file"""
    with open(json_file_path, 'r') as f:
        json_data = f.read()
    
    generator = MermaidERGenerator()
    return generator.generate_individual_diagram(json_data, database_name)

def save_diagram_to_file(diagram: str, output_file: str):
    """Save diagram to file"""
    with open(output_file, 'w') as f:
        f.write(diagram)
    print(f"Diagram saved to {output_file}")

# Example usage
if __name__ == "__main__":
    # Example 1: Generate complete diagram
    json_data = '''{"databases": [...]}'''  # Your JSON data here
    generator = MermaidERGenerator()
    
    try:
        # Complete diagram
        complete_diagram = generator.generate_complete_diagram(json_data)
        save_diagram_to_file(complete_diagram, "complete_diagram.mmd")
        
        # Individual database diagram
        identity_diagram = generator.generate_individual_diagram(json_data, "IdentityStore")
        save_diagram_to_file(identity_diagram, "identitystore_diagram.mmd")
        
        print("Diagrams generated successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

# One-liner functions for quick usage
def quick_generate_all(json_path: str, output_path: str = "diagram.mmd"):
    """One-liner to generate complete diagram"""
    diagram = generate_all_databases_diagram(json_path)
    save_diagram_to_file(diagram, output_path)
    return diagram

def quick_generate_db(json_path: str, db_name: str, output_path: str = None):
    """One-liner to generate specific database diagram"""
    if output_path is None:
        output_path = f"{db_name.lower()}_diagram.mmd"
    diagram = generate_database_diagram(json_path, db_name)
    save_diagram_to_file(diagram, output_path)
    return diagram
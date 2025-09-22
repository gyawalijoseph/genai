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
        columns_id = self._sanitize_id(table_name) + "_cols"

        # Table entity - just the table name as header
        lines.extend([
            f"    {table_id} {{",
            "    }",
            ""
        ])

        # Columns entity - just column entries, no header
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
                    columns_id = self._sanitize_id(unique_table_name) + "_cols"
                    lines.append(f"    {table_id} ||--o{{ {columns_id} : contains")

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

def generate_mermaid_from_json_payload(json_payload: Dict, application_id: str = None) -> str:
    """
    Generate Mermaid ER diagram from JSON payload dictionary

    Args:
        json_payload: Dictionary containing the JSON specification data
        application_id: Application identifier for the root node

    Returns:
        Generated Mermaid diagram as string
    """
    # Convert dict to JSON string for the generator
    json_data = json.dumps(json_payload)

    # Generate complete diagram
    generator = DynamicMermaidERGenerator(application_id)
    diagram = generator.generate_complete_diagram(json_data)

    return diagram

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

    # HARDCODED JSON PAYLOAD - Edit this section with your JSON data
    json_payload = {"databases": [
    {
      "databaseName": "IdentityStore",
      "bucketName": "IdentityStore",
      "clusterName": "E1,E2,E3 IPC1,E3 IPC2 Region 1,E3 IPC2 Region 2, E1,E1 Arena,E2,E2 Arena,E3 IPC2,E3 IPC1, , pdcbcl110007.aexp.com,deusw1cbecpsd000318.igdha-e2.aexp.com,lpqospdb51736.phx.aexp.com,lpqospdb51737.phx.aexp.com,lpqospdb51738.phx.aexp.com,lpqospdb51909.phx.aexp.com,lpqospdb51740.phx.aexp.com,lpqospdb51747.phx.aexp.com,lpqospdb51750.phx.aexp.com,lpqospdb51751.phx.aexp.com,lpqospdb51752.phx.aexp.com,pqcbcl00093.aexp.com,gpcbcl00051.aexp.com,ppcbcl00034.aexp.com,E1,E1 Arena,E2,E2 Arena,E3 IPC2,E3 IPC1,OPERATIONAL",
      "databaseType": "Couchbase",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "street_ln_1",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "postal_cd",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "gov_doc_ids",
              "datatype": "array"
            },
            {
              "CRUD": "read",
              "column_name": "phones",
              "datatype": "array"
            },
            {
              "CRUD": "read",
              "column_name": "email_addresses",
              "datatype": "array"
            },
            {
              "CRUD": "read",
              "column_name": "id_last_4",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "first_nm_first_3",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm_first_4",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "yob",
              "datatype": "int"
            },
            {
              "CRUD": "read",
              "column_name": "postal_cd_first_5",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "glbl_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "business_ids",
              "datatype": "object"
            },
            {
              "CRUD": "read",
              "column_name": "obligor",
              "datatype": "object"
            },
            {
              "CRUD": "read",
              "column_name": "legal",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "parent",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "parent_acct",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "acct_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "create_epoch_val",
              "datatype": "int"
            },
            {
              "CRUD": "read",
              "column_name": "epoch_val",
              "datatype": "int"
            },
            {
              "CRUD": "read",
              "column_name": "cm15",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "pcn",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "cm13",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "timestamp"
            },
            {
              "CRUD": "read",
              "column_name": "rel_id",
              "datatype": "string"
            }
          ],
          "table_name": "IdentityStore"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "identifiers.acct_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "identifiers.card.cm13",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "identifiers.card.cm15",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "identifiers.alt_acct_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "identifiers.clnt_origin_id",
              "datatype": "string"
            },
            {
              "CRUD": "update",
              "column_name": "identifiers.external",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "identifiers.external_ids",
              "datatype": "json"
            },
            {
              "CRUD": "read",
              "column_name": "typ.ctgy_typ_cd",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "typ.bu_cd",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "status.cd",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "status.purge_ind",
              "datatype": "string"
            },
            {
              "CRUD": "update",
              "column_name": "status",
              "datatype": "json"
            }
          ],
          "table_name": "account"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "business_ids.id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "business_ids.obligor.id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "business_ids.conglomerate_id.id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "business_ids.counterparty.identifier_details.id",
              "datatype": "string"
            },
            {
              "CRUD": "update",
              "column_name": "identifiers.external.dnb_information",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "external_ids.dnb",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "identifiers.external.pin_information",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "external_ids.pin",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "evaluation_details",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "business_ids.obligor.eval_dtls",
              "datatype": "json"
            },
            {
              "CRUD": "read",
              "column_name": "eval_details.mnl_Lnk_cd",
              "datatype": "string"
            }
          ],
          "table_name": "customer"
        },
        {
          "columns": [
            {
              "CRUD": "update",
              "column_name": "individual_information",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "individual_name",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "birth_information",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "date_of_birth",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "gender",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "embossed_information",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "emb_nm.individual",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "business_information",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "business_name.legal",
              "datatype": "json"
            },
            {
              "CRUD": "read",
              "column_name": "business_name.obligor",
              "datatype": "json"
            },
            {
              "CRUD": "read",
              "column_name": "business_name.obligor.nm",
              "datatype": "json"
            },
            {
              "CRUD": "update",
              "column_name": "government_document_identity",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "gov_doc_ids",
              "datatype": "array"
            }
          ],
          "table_name": "identity_profile"
        },
        {
          "columns": [
            {
              "CRUD": "update",
              "column_name": "postal_addresses",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "addresses",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "email_addresses",
              "datatype": "array"
            },
            {
              "CRUD": "update",
              "column_name": "telephones",
              "datatype": "array"
            }
          ],
          "table_name": "contact_profile"
        },
        {
          "columns": [
            {
              "CRUD": "update",
              "column_name": "bank_accounts",
              "datatype": "array"
            }
          ],
          "table_name": "bank_account_details"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "rel_id",
              "datatype": "string"
            }
          ],
          "table_name": "rel_id"
        }
      ],
      "queries": [
        "CREATE INDEX `IdentityStore_idx_Srch_9_sn` ON `IdentityStore`((distinct (array [(`v`.`street_ln_1`), (`v`.`postal_cd`)] for `v` in (`search_node`.`postal_addresses`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_7_sn` ON `IdentityStore`((distinct (array (`v`.`id`) for `v` in (`identity_profile`.`gov_doc_ids`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_6_sn` ON `IdentityStore`((distinct (array `v` for `v` in (`search_node`.`phones`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_5_sn` ON `IdentityStore`((distinct (array `v` for `v` in (`search_node`.`email_addresses`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_4_sn` ON `IdentityStore`((distinct (array (`v`.`id_last_4`) for `v` in (`identity_profile`.`gov_doc_ids`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_3_sn` ON `IdentityStore`((`search_node`.`first_nm_first_3`),(`search_node`.`lst_nm_first_4`),((`identity_profile`.`date_of_birth`).`yob`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_2_sn` ON `IdentityStore`((`search_node`.`first_nm_first_3`),(`search_node`.`lst_nm_first_4`),(distinct (array (`v`.`postal_cd_first_5`) for `v` in (`search_node`.`postal_addresses`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_1_sn_merge` ON `IdentityStore`((`search_node`.`first_nm_first_3`),(`search_node`.`lst_nm_first_4`),(distinct (array (`v`.`postal_cd_first_5`) for `v` in (`search_node`.`postal_addresses`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_19_sn` ON `IdentityStore`((distinct (array (`v`.`postal_cd_first_5`) for `v` in (`search_node`.`postal_addresses`) end)),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_18_sn` ON `IdentityStore`((`customer`.`glbl_id`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_17_sn` ON `IdentityStore`((`customer`.`id`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_16_sn` ON `IdentityStore`((((`customer`.`business_ids`).`obligor`).`id`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_15_sn` ON `IdentityStore`(((`customer`.`business_ids`).`glbl_ult`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_14_sn` ON `IdentityStore`(((`customer`.`business_ids`).`dom_ult`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_13_sn` ON `IdentityStore`(((`customer`.`business_ids`).`legal`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_12_sn` ON `IdentityStore`(((`customer`.`business_ids`).`parent`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_11_sn` ON `IdentityStore`(((`account`.`identifiers`).`parent_acct`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_Srch_10_sn` ON `IdentityStore`(((`account`.`identifiers`).`acct_id`),`id`) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n9` ON `IdentityStore`(((`account`.`status`).`create_epoch_val`)) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n8` ON `IdentityStore`((`last_update_timestamp`.`epoch_val`)) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n7` ON `IdentityStore`((((`account`.`identifiers`).`card`).`cm15`)) WITH { \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n6` ON `IdentityStore`(((`account`.`setup_references`).`pcn`)) WITH { \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n5` ON `IdentityStore`(((`account`.`identifiers`).`parent_acct`)) WITH { \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n4` ON `IdentityStore`((((`account`.`identifiers`).`card`).`cm13`)) WITH { \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n3` ON `IdentityStore`((`customer`.`id`),`customer.typ`) WITH { \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n10` ON `IdentityStore`((`evaluation_details`.`lst_updt_ts`)) WITH { \"defer_build\":true, \"num_replica\":1 }",
        "CREATE INDEX `IdentityStore_idx_n1` ON `IdentityStore`(`rel_id`) WITH { \"num_replica\":1 }",
        "select customer.id, customer.glbl_id from `IdentityStore` use keys '${rowKey}'",
        "select meta().id as metaId from %{bucket} where customer.id='${customer_id}' limit xxxxx",
        "select meta().id as metaId from %{bucket} where customer.business_ids.id='${business_id}' limit xxxxx",
        "select meta().id as metaId from %{bucket} where customer.business_ids.obligor.id='${obligor_id}' limit xxxxx",
        "select meta().id as metaId from %{bucket} where account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND account.identifiers.card.cm13=\"${acct_id}\"",
        "select meta().id as metaId from %{bucket} where account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND account.identifiers.card.cm15=\"${acct_id}\"",
        "select meta().id as metaId, account.typ.ctgy_typ_cd, account.typ.bu_cd as bu_cd from %{bucket} where account.identifiers.acct_id = \"null\" and account.typ.ctgy_typ_cd != \"TPR\" limit 1",
        "select meta().id as metaId, account.typ.ctgy_typ_cd, account.typ.bu_cd as bu_cd from %{bucket} where account.identifiers.acct_id = \"xxxxx\" and account.typ.ctgy_typ_cd != \"TPR\" limit 1",
        "select meta().id as metaId, rel_id, customer.id as customerId, identity_profile from %{bucket} where account.identifiers.acct_id=\"${id}\" AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND typ=\"${type}\"",
        "select meta().id as acct_id from %{bucket} where account.identifiers.acct_id=\"${id}\" AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\"",
        "select meta().id as metaId, account.identifiers.acct_id as acct_id from %{bucket} where rel_id=\"${id}\"",
        "select meta().id as metaId from %{bucket} where account.identifiers.acct_id=\"${id}\" AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND typ=\"${type}\"",
        "select meta().id as metaId from %{bucket} where customer.id='${customer_id}'",
        "select meta().id as metaId from %{bucket} where customer.business_ids.id='${business_id}'",
        "select meta().id as metaId from %{bucket} where customer.business_ids.obligor.id='${obligor_id}'",
        "account_external_update=JSON_JSON,$.account.identifiers.external,$.account.identifiers.external_ids",
        "status_update=JSON_JSON,$.account.status,$.account.status",
        "customer_external_dnb_update=JSON_JSON,$.customer.identifiers.external.dnb_information,$.customer.external_ids.dnb",
        "customer_evaluation_details_update=JSON_JSON,$.customer.evaluation_details,$.customer.business_ids.obligor.eval_dtls",
        "customer_external_pin_update=JSON_ARRAY,$.customer.identifiers.external.pin_information,$.customer.external_ids.pin",
        "evaluation_details_update=JSON_JSON,$.evaluation_details,$.evaluation_details",
        "individual_information_update=DERIVED_JSON_JSON,$.identity_profile.individual_information,$.identity_profile.individual_name",
        "birth_date_update=JSON_JSON,$.identity_profile.birth_information,$.identity_profile.date_of_birth",
        "gender_update=JSON_JSON,$.identity_profile.gender,$.identity_profile.gender",
        "embossed_information_update=JSON_JSON,$.identity_profile.embossed_information,$.identity_profile.emb_nm.individual",
        "business_information_update=JSON_JSON,$.identity_profile.business_information,$.identity_profile.business_name.legal",
        "government_document_identity_update=ARRAY_JSON,$.identity_profile.government_document_identity,$.identity_profile.gov_doc_ids",
        "postal_addresses_update=ARRAY_JSON,$.contact_profile.postal_addresses,$.contact_profile.addresses",
        "email_addresses_update=ARRAY_JSON,$.contact_profile.email_addresses,$.contact_profile.email_addresses",
        "telephones_update=ARRAY_JSON,$.contact_profile.telephones,$.contact_profile.telephones",
        "bank_account_details_update=ARRAY_JSON,$.bank_account_details,$.bank_accounts",
        "select meta().id as metaId, account.typ.ctgy_typ_cd as categoryCode from %{bucket} where account.identifiers.acct_id in ${ids} AND account.typ.ctgy_typ_cd in [\"CRD\", \"OLN\", \"CLN\"] AND typ in [\"BASIC\", \"SUPP\"]",
        "select meta().id as metaId, rel_id, customer.id as customerId, customer.business_ids.id as businessId, identity_profile, account.status.cd as statusCode from %{bucket} where account.identifiers.acct_id in ${ids} AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND typ=\"${type}\"",
        "select meta().id as acct_id from %{bucket} where account.identifiers.acct_id in ${ids} AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\"",
        "select meta().id as metaId, customer.id as customerId from %{bucket} where account.identifiers.acct_id in ${ids} AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND typ=\"${type}\"",
        "select meta().id as metaId, account.typ.ctgy_typ_cd as categoryCode from %{bucket} where account.identifiers.alt_acct_id=\"${id}\" AND account.typ.ctgy_typ_cd in [\"PSA\", \"CCH\"] AND typ in [\"PRI\"]",
        "select meta().id as metaId from %{bucket} where account.identifiers.alt_acct_id=\"${id}\" AND account.typ.ctgy_typ_cd=\"${ctgy_cd}\" AND typ=\"${type}\"",
        "select meta().id as metaId, account.identifiers.acct_id as acct_id, customer.id as customerId from %{bucket} where rel_id=\"${id}\"",
        "(select meta().id as metaId, rel_id as relId from %{bucket} where rel_id=\"${rel_id}\") union (select meta().id as metaId, rel_id as relId from %{bucket} where customer.business_ids.id=\"${id}\" and account.typ.ctgy_typ_cd='SUP' and account.status.purge_ind is MISSING)",
        "select meta().id as metaId from %{bucket} where account.identifiers.clnt_origin_id in ${ids}",
        "select meta().id as metaId from %{bucket} where customer.id IN [\"713806664401\",\"513328417404\"] limit 60",
        "select meta().id as metaId from %{bucket} where customer.id IN [\"713806664401\"] limit 60",
        "select meta().id as rowId, account.identifiers.acct_id as acct_id , account.typ.ctgy_typ_cd as ctgy_cd, typ as type, customer.eval_details.mnl_Lnk_cd as mnl_lnk_cd from %{bucket} where customer.id=\"${id}\"",
        "select count(*) as acct_count from %{bucket} where customer.business_ids.id=\"${id}\" and account.status.purge_ind is MISSING",
        "select count(*) as acct_count from %{bucket} where customer.business_ids.obligor.id=\"${id}\" and account.status.purge_ind is MISSING",
        "select count(*) as acct_count from %{bucket} where customer.business_ids.conglomerate_id.id=\"${id}\" and account.status.purge_ind is MISSING",
        "SELECT identity_profile.business_name.obligor AS obligorName FROM %{bucket} WHERE customer.business_ids.obligor.id = $obligorId AND identity_profile.business_name.obligor.nm IS VALUED AND account.status.purge_ind IS MISSING LIMIT 1",
        "SELECT customer.business_ids.counterparty.identifier_details.id AS counterpartyId FROM %{bucket} WHERE customer.business_ids.obligor.id = $obligorId AND customer.business_ids.counterparty.identifier_details.id IS VALUED AND account.status.purge_ind IS MISSING LIMIT 1"
      ],
      "serverHost": "lpdospdbb50263.phx.aexp.com,lpqospdb51736.phx.aexp.com,lppospdbb50267.phx.aexp.com,lgpospdbb60384.gso.aexp.com, lpdospdb51328.phx.aexp.com, lpdospdb51332.phx.aexp.com, lpdospdb51333.phx.aexp.com, pqcbcl00093.aexp.com, gpcbcl00051.aexp.com, ppcbcl00034.aexp.com, , pdcbcl110007.aexp.com,deusw1cbecpsd000318.igdha-e2.aexp.com,lpqospdb51736.phx.aexp.com,lpqospdb51737.phx.aexp.com,lpqospdb51738.phx.aexp.com,lpqospdb51909.phx.aexp.com,lpqospdb51740.phx.aexp.com,lpqospdb51747.phx.aexp.com,lpqospdb51750.phx.aexp.com,lpqospdb51751.phx.aexp.com,lpqospdb51752.phx.aexp.com,pqcbcl00093.aexp.com,gpcbcl00051.aexp.com,ppcbcl00034.aexp.com,lpdospdb51328.phx.aexp.com,lpdospdb51332.phx.aexp.com,lpdospdb51333.phx.aexp.com,lpdospdbb50263.phx.aexp.com",
      "replicaSet": "2, ",
      "schemaName": ""
    },
    {
      "databaseName": "customerdb",
      "clusterName": "prod-cluster, customer-cluster",
      "databaseType": "PostgreSQL",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read,write,update,delete",
              "column_name": "id",
              "datatype": "unknown"
            },
            {
              "CRUD": "write",
              "column_name": "name",
              "datatype": "unknown"
            },
            {
              "CRUD": "write,update",
              "column_name": "email",
              "datatype": "unknown"
            }
          ],
          "table_name": "customers"
        },
        {
          "columns": [
            {
              "CRUD": "read,update,delete",
              "column_name": "id",
              "datatype": "integer"
            },
            {
              "CRUD": "write",
              "column_name": "name",
              "datatype": "string"
            },
            {
              "CRUD": "write,update",
              "column_name": "email",
              "datatype": "string"
            }
          ],
          "table_name": "customers"
        }
      ],
      "queries": [
        "SELECT * FROM customers WHERE id = ?",
        "INSERT INTO customers (name, email) VALUES (?, ?)",
        "UPDATE customers SET email = ? WHERE id = ?",
        "DELETE FROM customers WHERE id = ?"
      ],
      "schemaName": "public",
      "serverHost": "db-prod.example.com"
    },
    {
      "databaseName": "analytics",
      "bucketName": "user_events, events",
      "clusterName": "analytics-cluster",
      "databaseType": "MongoDB",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read,write",
              "column_name": "userId",
              "datatype": "unknown"
            },
            {
              "CRUD": "write",
              "column_name": "event",
              "datatype": "unknown"
            }
          ],
          "table_name": "user_events"
        },
        {
          "columns": [
            {
              "CRUD": "read,write",
              "column_name": "type",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "user",
              "datatype": "string"
            }
          ],
          "table_name": "events"
        }
      ],
      "queries": [
        "db.user_events.find({\"userId\": ?})",
        "db.user_events.insert({\"userId\": ?, \"event\": ?})",
        "db.events.find({\"type\": \"purchase\"})",
        "db.events.insert({\"type\": \"login\", \"user\": \"user1\"})"
      ],
      "replicaSet": "rs0",
      "serverHost": "mongo-analytics.example.com, mongo-prod.example.com"
    },
    {
      "databaseName": "contact_profile",
      "databaseType": "unknown",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "bounce_bk_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "bounce_bk_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "email_ad",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.hash_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "verf_sta",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "business"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "bounce_bk_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "bounce_bk_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "email_ad",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.hash_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "verf_sta",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "estatement"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "bounce_bk_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "bounce_bk_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "email_ad",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.hash_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "verf_sta",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "other"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "bounce_bk_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "bounce_bk_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "email_ad",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.hash_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "verf_sta",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "security"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "bounce_bk_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "bounce_bk_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "dsgntn_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "email_ad",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.hash_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "hash_email.lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_verf_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "verf_sta",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "servicing"
        }
      ],
      "queries": [
        "SELECT business.bounce_bk_dt, business.bounce_bk_ind, business.dsgntn_src, business.dsgntn_ts, business.dsgntn_typ, business.email_ad, business.hash_email.hash_nbr, business.hash_email.lst_updt_src, business.hash_email.lst_updt_ts, business.lst_verf_src, business.lst_verf_ts, business.lst_verf_usr, business.verf_sta, business.typ FROM contact_profile.email_addresses.business",
        "SELECT estatement.bounce_bk_dt, estatement.bounce_bk_ind, estatement.dsgntn_src, estatement.dsgntn_ts, estatement.dsgntn_typ, estatement.email_ad, estatement.hash_email.hash_nbr, estatement.hash_email.lst_updt_src, estatement.hash_email.lst_updt_ts, estatement.lst_verf_src, estatement.lst_verf_ts, estatement.lst_verf_usr, estatement.verf_sta, estatement.typ FROM contact_profile.email_addresses.estatement",
        "SELECT other.bounce_bk_dt, other.bounce_bk_ind, other.dsgntn_src, other.dsgntn_ts, other.dsgntn_typ, other.email_ad, other.hash_email.hash_nbr, other.hash_email.lst_updt_src, other.hash_email.lst_updt_ts, other.lst_verf_src, other.lst_verf_ts, other.lst_verf_usr, other.verf_sta, other.typ FROM contact_profile.email_addresses.other",
        "SELECT security.bounce_bk_dt, security.bounce_bk_ind, security.dsgntn_src, security.dsgntn_ts, security.dsgntn_typ, security.email_ad, security.hash_email.hash_nbr, security.hash_email.lst_updt_src, security.hash_email.lst_updt_ts, security.lst_verf_src, security.lst_verf_ts, security.lst_verf_usr, security.verf_sta, security.typ FROM contact_profile.email_addresses.security",
        "SELECT servicing.bounce_bk_dt, servicing.bounce_bk_ind, servicing.dsgntn_src, servicing.dsgntn_ts, servicing.dsgntn_typ, servicing.email_ad, servicing.hash_email.hash_nbr, servicing.hash_email.lst_updt_src, servicing.hash_email.lst_updt_ts, servicing.lst_verf_ts, servicing.lst_verf_src, servicing.lst_verf_usr, servicing.verf_sta, servicing.typ FROM contact_profile.email_addresses.servicing"
      ],
      "schemaName": "email_addresses"
    },
    {
      "databaseName": "identity_profile",
      "databaseType": "unknown",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "primary",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "residential_status",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "secondary",
              "datatype": "unknown"
            }
          ],
          "table_name": "nationality"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm_lang_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "relationship_names"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm_lang_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "pfx_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "suff_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "title",
              "datatype": "unknown"
            }
          ],
          "table_name": "external"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "addtl_lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "title",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "suff_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_first_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_full_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_lst_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_mid_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "pfx_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "first_nm",
              "datatype": "unknown"
            }
          ],
          "table_name": "other"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "addtl_lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "title",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "suff_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_first_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_full_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_lst_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_mid_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_flg",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "pfx_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "prfrd_first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm_lang_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "initials",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "full_nm",
              "datatype": "unknown"
            }
          ],
          "table_name": "primary"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "addtl_lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "initials",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm_lang_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "prfrd_first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "pfx_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_flg",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.full_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.first_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_mid_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_lst_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.mid_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.lst_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_first_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_full_nm_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "suff_nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "title",
              "datatype": "unknown"
            }
          ],
          "table_name": "secondary"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_flg",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_ind",
              "datatype": "unknown"
            }
          ],
          "table_name": "company"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_flg",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "smrt_demo_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "processed.std_ind",
              "datatype": "unknown"
            }
          ],
          "table_name": "individual"
        }
      ],
      "queries": [
        "SELECT nationality.lst_updt_src, nationality.lst_updt_ts, nationality.primary, nationality.residential_status, nationality.secondary FROM identity_profile.nationality",
        "SELECT relationship_names.first_nm, relationship_names.full_nm, relationship_names.lst_nm, relationship_names.lst_updt_src, relationship_names.lst_updt_ts, relationship_names.mid_nm, relationship_names.nm_lang_ind, relationship_names.typ FROM identity_profile.relationship_names",
        "SELECT external.first_nm, external.full_nm, external.lst_nm, external.lst_updt_src, external.lst_updt_ts, external.nm_lang_ind, external.mid_nm, external.pfx_nm, external.suff_nm, external.title FROM identity_profile.individual_name.external",
        "SELECT other.addtl_lst_nm, other.typ, other.title, other.suff_nm, other.processed.first_nm, other.processed.full_nm, other.processed.lst_nm, other.processed.mid_nm, other.processed.std_first_nm_ind, other.processed.std_full_nm_ind, other.processed.std_lst_nm_ind, other.processed.std_mid_nm_ind, other.pfx_nm, other.mid_nm, other.lst_updt_usr, other.lst_updt_ts, other.lst_updt_src, other.lst_nm, other.full_nm, other.first_nm FROM identity_profile.individual_name.other",
        "SELECT primary.addtl_lst_nm, primary.first_nm, primary.title, primary.suff_nm, primary.processed.first_nm, primary.processed.full_nm, primary.processed.lst_nm, primary.processed.mid_nm, primary.processed.std_first_nm_ind, primary.processed.std_full_nm_ind, primary.processed.std_lst_nm_ind, primary.processed.std_mid_nm_ind, primary.smrt_demo_updt_ts, primary.smrt_demo_flg, primary.pfx_nm, primary.prfrd_first_nm, primary.nm_lang_ind, primary.mid_nm, primary.lst_updt_usr, primary.lst_updt_ts, primary.lst_updt_src, primary.lst_nm, primary.initials, primary.full_nm FROM identity_profile.individual_name.primary",
        "SELECT secondary.addtl_lst_nm, secondary.first_nm, secondary.initials, secondary.full_nm, secondary.lst_nm, secondary.lst_updt_src, secondary.lst_updt_ts, secondary.lst_updt_usr, secondary.mid_nm, secondary.nm_lang_ind, secondary.prfrd_first_nm, secondary.pfx_nm, secondary.smrt_demo_flg, secondary.smrt_demo_updt_ts, secondary.processed.full_nm, secondary.processed.first_nm, secondary.processed.std_mid_nm_ind, secondary.processed.std_lst_nm_ind, secondary.processed.mid_nm, secondary.processed.lst_nm, secondary.processed.std_first_nm_ind, secondary.processed.std_full_nm_ind, secondary.suff_nm, secondary.title FROM identity_profile.individual_name.secondary",
        "SELECT company.lst_updt_src, company.lst_updt_ts, company.nm, company.smrt_demo_flg, company.smrt_demo_updt_ts, company.processed.nm, company.processed.std_ind FROM identity_profile.emb_nm.company",
        "SELECT individual.lst_updt_src, individual.lst_updt_ts, individual.nm, individual.smrt_demo_flg, individual.smrt_demo_updt_ts, individual.processed.nm, individual.processed.std_ind FROM identity_profile.emb_nm.individual"
      ],
      "schemaName": "identity_profile, unknown, individual_name, emb_nm"
    },
    {
      "databaseName": "unknown",
      "databaseType": "unknown, Couchbase, Elasticsearch, POSTGRESQL",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "curr_typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lang_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            }
          ],
          "table_name": "preferences"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "email_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "address",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "phone",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "relationship_managers"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "incident_nbr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_reval_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_usr",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_rsn_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mnl_Lnk_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "mnl_rsn_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lnk_reval_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "reval_rsn_cd",
              "datatype": "unknown"
            }
          ],
          "table_name": "eval_details"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "customer",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "identity_profile",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.status.member_since_dt",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.status.member_since_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.acct_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.status.cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.typ.ctgy_typ_cd",
              "datatype": "unknown"
            }
          ],
          "table_name": "%{bucket}"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "rel_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "identity_profile",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.glbl_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.cas_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.typ.ctgy_typ_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.status.purge_ind",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.status.cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.profiles",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.acct_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.alt_acct_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.clnt_origin_id",
              "datatype": "unknown"
            }
          ],
          "table_name": "%{bucket}"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "identity_profile.gov_doc_ids",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.business_ids.obligor.id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "identity_profile.business_name.obligor",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "tinId",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.business_ids.obligor.eval_dtls.mnl_Lnk_cd",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "identity_profile.business_name.obligor.nm",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "customer.business_ids.counterparty.identifier_details.id",
              "datatype": "unknown"
            }
          ],
          "table_name": "%{bucket}"
        }
      ],
      "queries": [
        "SELECT curr_typ, lang_cd, lst_updt_ts, lst_updt_src FROM preferences",
        "SELECT email_id, lst_updt_src, lst_updt_ts, nm, address, phone, typ FROM relationship_managers",
        "SELECT incident_nbr, lst_reval_ts, lst_updt_src, lst_updt_usr, lst_updt_rsn_cd, lst_updt_ts, mnl_Lnk_cd, mnl_rsn_cd, lnk_reval_ind, reval_rsn_cd FROM customer.eval_details",
        "SELECT rowKeys.rowId as rowId From ( SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.telephones SATISFIES v IN $phone END AND account.status.purge_ind IS MISSING ) as rowKeys LIMIT xxxxx",
        "(SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk2 SATISFIES u = $icsk2 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in identity_profile.gov_doc_ids SATISFIES v.id = $icsk6 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx)",
        "SELECT rowKeys.rowId as rowId From ( (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk2 SATISFIES u = $icsk2 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in identity_profile.gov_doc_ids SATISFIES v.id = $icsk6 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) ) as rowKeys LIMIT xxxxx",
        "(SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u = $icsk1 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx) UNION (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk2 SATISFIES u = $icsk2 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx) UNION (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk3 SATISFIES u = $icsk3 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.telephones SATISFIES v = $icsk5 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in identity_profile.gov_doc_ids SATISFIES v.id = $icsk6 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', ''] LIMIT xxxxx)",
        "(SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u = $icsk1 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk2 SATISFIES u = $icsk2 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.telephones SATISFIES v = $icsk5 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx)",
        "(SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u = $icsk1 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk2 SATISFIES u = $icsk2 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk3 SATISFIES u = $icsk3 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.telephones SATISFIES v = $icsk5 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx) UNION (SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in identity_profile.gov_doc_ids SATISFIES v.id = $icsk6 END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''] LIMIT xxxxx)",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[0] IN ['${first_name_first_3}', '${last_name_first_4}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[1] IN ['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[2] IN ['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[0]=['${first_name_first_3}', '${last_name_first_4}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[1]=['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_3, v.lst_nm_4] for `v` IN `search_node`.`individual_names` END)[2]=['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY v.id_last4 for `v` IN `identity_profile`.`gov_doc_ids` WHEN `v`.`typ` = 'SSN' END)[0] = '${ssn_last_4}' AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END LIMIT xxxxx",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.individual_names SATISFIES [v.first_nm_3, v.lst_nm_4] = ['${first_name_first_3}', '${last_name_first_4}'] END AND identity_profile.date_of_birth.yob=\"${yob}\" LIMIT xxxxx",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.email_addresses SATISFIES v IN ${email} END LIMIT xxxxx",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.telephones SATISFIES v IN ${phone} END LIMIT xxxxx",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in identity_profile.gov_doc_ids SATISFIES [v.id, v.typ] = [${gov_doc_id}, ${gov_doc_id_type}] END LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_4, v.lst_nm_5] for `v` IN `search_node`.`individual_names` END)[0] IN ['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_4, v.lst_nm_5] for `v` IN `search_node`.`individual_names` END)[1] IN ['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT META().id as rowId FROM `%{bucket}` WHERE (ARRAY [v.first_nm_4, v.lst_nm_5] for `v` IN `search_node`.`individual_names` END)[2] IN ['${first_name_first_4}', '${last_name_first_5}'] AND ANY u IN search_node.postal_addresses SATISFIES `u`.`postal_cd_5` IN ${postal_code_first_5} END  LIMIT xxxxx",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v IN search_node.individual_names SATISFIES [v.first_nm_4, v.lst_nm_5] = ['${first_name_first_4}', '${last_name_first_5}'] END AND identity_profile.date_of_birth.yob=\"${yob}\" LIMIT xxxxx",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE ANY v IN search_node.individual_names SATISFIES v.first_nm = $first_name_subQuery AND v.lst_nm = $last_name_subQuery END AND account.status.purge_ind IS MISSING )",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE ANY v IN search_node.individual_names SATISFIES v.first_nm = $first_name_subQuery END AND account.status.purge_ind IS MISSING )",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE ANY v IN search_node.individual_names SATISFIES v.lst_nm = $last_name_subQuery END AND account.status.purge_ind IS MISSING )",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.city_nm IN $city_subQuery OR contact_profile.postal_addresses.home.city_nm IN $city_subQuery) AND account.status.purge_ind IS MISSING)",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.state IN $state_subQuery OR contact_profile.postal_addresses.home.state IN $state_subQuery) AND account.status.purge_ind IS MISSING)",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.ctry_cd IN $country_code_subQuery OR contact_profile.postal_addresses.home.ctry_cd IN $country_code_subQuery) AND account.status.purge_ind IS MISSING)",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.postal_cd IN $postal_code_subQuery OR contact_profile.postal_addresses.home.postal_cd IN $postal_code_subQuery) AND account.status.purge_ind IS MISSING)",
        "SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW meta().id as rowId FROM %{bucket} WHERE ANY u IN search_node.i_csk1 SATISFIES u LIKE $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''])  WHERE identity_profile.date_of_birth.yob = $yob_subQuery AND account.status.purge_ind IS MISSING",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE ANY v IN search_node.individual_names SATISFIES v.first_nm IN $first_name_subQuery END AND account.status.purge_ind IS MISSING )",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE ANY v IN search_node.individual_names SATISFIES v.lst_nm IN $last_name_subQuery END AND account.status.purge_ind IS MISSING )",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.city_nm IN $city_subQuery OR contact_profile.postal_addresses.home.city_nm IN $city_subQuery) AND account.status.purge_ind IS MISSING)",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.state IN $state_subQuery OR contact_profile.postal_addresses.home.state IN $state_subQuery) AND account.status.purge_ind IS MISSING)",
        "(SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW META().id as rowId FROM `%{bucket}` WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', '']) WHERE (contact_profile.postal_addresses.business.ctry_cd IN $country_code_subQuery OR contact_profile.postal_addresses.home.ctry_cd IN $country_code_subQuery) AND account.status.purge_ind IS MISSING)",
        "SELECT meta().id as rowId FROM %{bucket} USE KEYS (SELECT RAW meta().id as rowId FROM %{bucket} WHERE ANY u IN search_node.i_csk1 SATISFIES u IN $icsk1_subQuery END AND account.status.purge_ind IS MISSING AND (UPPER((`customer`.`typ`)) IN ['INDIVIDUAL', 'BOTH']) AND IFMISSING(customer.eval_details.mnl_Lnk_cd, '') IN ['M', 'V', ''])  WHERE identity_profile.date_of_birth.yob IN $yob_subQuery AND account.status.purge_ind IS MISSING",
        "openPointInTime(OpenPointInTimeRequest.of(pit -> pit.index(index).keepAlive(Time.of(t -> t.time(POINT_IN_TIME_KEEP_ALIVE_DURATION)))))",
        "search(searchRequest, Relationship.class)",
        "buildTermQuery(\"account.typ.region.mkt.alpha_cd\", marketFilter)",
        "callBuildExactRelationshipQuery(queryValues)",
        "mergeBusinessRuleBasedSearchQuery(filterQuery, subQuery)",
        "MsearchRequest.of(msr -> msr.searches(requestItems))",
        "msearch(msearchRequest, Relationship.class)",
        "select customer, identity_profile, account.status.member_since_dt, account.status.member_since_ind from %{bucket} where account.identifiers.acct_id=\"${id}\"",
        "select customer, account.status.member_since_dt, account.status.member_since_ind from %{bucket} where account.identifiers.acct_id=\"${id}\"",
        "select customer, identity_profile, account.status.member_since_dt, account.status.member_since_ind from %{bucket} where account.identifiers.acct_id=\"${id}\" and typ=\"${typ}\" and account.status.cd IN [\"A\",\"0\",\"00\"] and account.typ.ctgy_typ_cd=\"${ctgy_typ_cd}\"",
        "select meta().id as rel_id, identity_profile as identityProfile, customer.glbl_id as globalId, customer.id as customerId, customer.cas_id as casIdentifier, account.typ.ctgy_typ_cd as categoryCode, typ as roleCode, account.status.purge_ind as purgeInd, account.status.cd as statusCode from %{bucket} where account.identifiers.acct_id=\"${acct_id}\" and typ=\"${typ}\" and account.typ.ctgy_typ_cd=\"${ctgy_typ_cd}\"",
        "select rel_id, customer.glbl_id as globalId, customer.id as customerId, customer.profiles as customerProfiles, typ as roleCode from %{bucket} where account.identifiers.acct_id=\"${acct_id}\" and typ=\"${typ}\" and account.typ.ctgy_typ_cd=\"${ctgy_typ_cd}\" and (account.status.purge_ind!=\"Y\" or account.status.purge_ind is not valued)",
        "select meta().id as rel_id,identity_profile as identityProfile, customer.glbl_id as globalId, customer.id as customerId, account.typ.ctgy_typ_cd as categoryCode, typ as roleCode from %{bucket} where account.identifiers.acct_id=\"${acct_id}\" and typ=\"${typ}\"",
        "select meta().id as rel_id, customer.glbl_id as globalId, customer.id as customerId from %{bucket} where account.identifiers.acct_id=\"${acct_id}\" and typ=\"${typ}\" and account.typ.ctgy_typ_cd=\"${ctgy_typ_cd}\" and account.identifiers.alt_acct_id=\"${alt_acct_id}\" and (account.status.purge_ind!=\"Y\" or account.status.purge_ind is not valued)",
        "select meta().id as rel_id, customer.glbl_id as globalId, customer.id as customerId from %{bucket} where account.identifiers.acct_id=\"${acct_id}\" and typ=\"${typ}\" and account.typ.ctgy_typ_cd=\"${ctgy_typ_cd}\" and account.identifiers.alt_acct_id=\"${alt_acct_id}\" and account.identifiers.clnt_origin_id=\"${clnt_origin_id}\" and (account.status.purge_ind!=\"Y\" or account.status.purge_ind is not valued)",
        "SELECT identity_profile.gov_doc_ids AS govDocIds, customer.business_ids.obligor.id AS obligorId, identity_profile.business_name.obligor as obligorName, $tinId as encryptedTargetTaxId FROM %{bucket} WHERE customer.business_ids.obligor.id IS VALUED AND ANY v in identity_profile.gov_doc_ids SATISFIES [v.typ, IFMISSINGORNULL(v.processed.id, v.id)] in [['TIN',$tinId],['EIN',$tinId],['ABN',$tinId],['SSN',$tinId]] END AND account.status.purge_ind IS MISSING AND (customer.business_ids.obligor.eval_dtls.mnl_Lnk_cd != 'X' OR customer.business_ids.obligor.eval_dtls.mnl_Lnk_cd IS NOT VALUED) limit 200",
        "SELECT identity_profile.business_name.obligor AS obligorName FROM %{bucket} WHERE customer.business_ids.obligor.id = $obligorId AND identity_profile.business_name.obligor.nm IS VALUED AND account.status.purge_ind IS MISSING LIMIT 1",
        "SELECT customer.business_ids.counterparty.identifier_details.id AS counterpartyId FROM %{bucket} WHERE customer.business_ids.obligor.id = $obligorId AND customer.business_ids.counterparty.identifier_details.id IS VALUED AND account.status.purge_ind IS MISSING LIMIT 1"
      ],
      "schemaName": "preferences, customer, unknown",
      "bucketName": "%{bucket}",
      "serverHost": "unknown",
      "clusterName": "unknown",
      "replicaSet": "unknown"
    },
    {
      "databaseName": "digital_profile",
      "databaseType": "unknown",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "ip",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            }
          ],
          "table_name": "ip_addresses"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "ip",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "std_ind",
              "datatype": "unknown"
            }
          ],
          "table_name": "ip_addresses.processed"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_src",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "lst_updt_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "typ",
              "datatype": "unknown"
            }
          ],
          "table_name": "devices"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "unknown"
            },
            {
              "CRUD": "read",
              "column_name": "std_ind",
              "datatype": "unknown"
            }
          ],
          "table_name": "devices.processed"
        }
      ],
      "queries": [
        "SELECT ip, lst_updt_src, lst_updt_ts FROM digital_profile.ip_addresses",
        "SELECT ip FROM digital_profile.ip_addresses.processed",
        "SELECT std_ind FROM digital_profile.ip_addresses.processed",
        "SELECT id FROM devices",
        "SELECT lst_updt_src FROM devices",
        "SELECT lst_updt_ts FROM devices",
        "SELECT id FROM devices.processed",
        "SELECT std_ind FROM devices.processed",
        "SELECT typ FROM devices"
      ],
      "schemaName": "digital_profile"
    },
    {
      "databaseName": "IdentityStore_Hiped",
      "bucketName": "IdentityStore_Hiped",
      "clusterName": "OPERATIONAL, , unknown",
      "databaseType": "Couchbase",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "IdentityStore_Hiped"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            }
          ],
          "table_name": "IdentityStore_Hiped"
        },
        {
          "columns": [],
          "table_name": "IdentityStore_Hiped"
        }
      ],
      "queries": [
        "DELETE FROM IdentityStore_Hiped",
        "select meta().id as id from IdentityStore_Hiped"
      ],
      "replicaSet": "",
      "schemaName": "",
      "serverHost": "couchbaseContainer.getConnectionString(), unknown"
    },
    {
      "databaseName": "DataCacheStore",
      "bucketName": "DataCacheStore",
      "clusterName": "DATACACHESTORE, unknown",
      "databaseType": "Couchbase",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            }
          ],
          "table_name": "DataCacheStore"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "levelId",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "acctId",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "parentAcct",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "idType",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "altAcctId",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "purgeInd",
              "datatype": "boolean"
            },
            {
              "CRUD": "read",
              "column_name": "rel_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.card.cm13",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.card.cm11",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.corp_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "account.identifiers.clnt_origin_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "account.typ.ctgy_typ_cd",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "customer.profiles",
              "datatype": "array"
            }
          ],
          "table_name": "DataCacheStore"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "DataCacheStore.C360.Customer"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "DataCacheStore.C360.Account"
        }
      ],
      "queries": [
        "DELETE FROM DataCacheStore",
        "select meta().id as rowId, ${levelId} as ids from %{bucket} where any v in [${levelId}, ${acctId}] satisfies v in $id END${catCdFilter} limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} where any v in [${levelId}, ${acctId}] satisfies v in $ids END${catCdFilter}${typFilter} limit $limit offset $offset",
        "select ${acctId} as ids from %{bucket} where ${idType} in $id limit $limit offset $offset",
        "select meta().id as rowId, ${parentAcct} as ids from %{bucket} where any v in [${parentAcct}, ${acctId}] satisfies v in $ids END${catCdFilter} limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} where any v in [${parentAcct}, ${acctId}] satisfies v in $ids END${catCdFilter}${typFilter} limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} where ${idType}=$id${catCdFilter}${typFilter} limit $limit offset $offset",
        "select ${acctId} as id from %{bucket} where ${relId}=$id limit $limit",
        "select ${acctId} as ids from %{bucket} WHERE ${altAcctId}=$id AND ${purgeInd} IS MISSING limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} where ${levelId} in $ids${catCdFilter}${typFilter} limit $limit offset $offset",
        "select ${levelId} as ids from %{bucket} where ${idType}=$id AND ${purgeInd} IS MISSING limit $limit offset $offset",
        "select ${levelId} as ids from %{bucket} where ${idType} in $id limit xxxxx",
        "select ${levelId} as ids from %{bucket} where account.typ.ctgy_typ_cd in ['MCA', 'BCA'] and ${idType}=$id",
        "select ${levelId} as id from %{bucket} where ${idType}=$id limit xxxxx",
        "select meta().id as rowId from %{bucket} where ${levelId}=$id${catCdFilter}${typFilter} limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} where ${idType} in $ids${catCdFilter}${typFilter} limit $limit offset $offset",
        "select meta().id as rowId from %{bucket} USE KEYS $metaId",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ${altAcctId} in $ids${catCdFilter}${typFilter} AND ${purgeInd} IS MISSING limit $limit offset $offset",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ${altAcctId}=$id${catCdFilter}${typFilter} AND ${purgeInd} IS MISSING limit $limit offset $offset",
        "SELECT meta().id as rowId FROM %{bucket} WHERE ANY v in customer.profiles SATISFIES [v.id, v.typ] = [$id, ${typeOfId}] END${catCdFilter}${typFilter} AND ${purgeInd} IS MISSING limit $limit offset $offset",
        "select meta().id from %{bucket} where any v in [@levelId, account.identifiers.acct_id] satisfies v in $inputIds end and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in [@levelId, account.identifiers.acct_id] satisfies v in $acctIds end and account.status.purge_ind is missing",
        "select meta().id from %{bucket} where account.identifiers.card.cm13 in $inputIds and account.status.purge_ind is missing",
        "select meta().id from %{bucket} where account.identifiers.card.cm11 in $inputIds and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where account.identifiers.corp_id in $inputIds and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where account.identifiers.clnt_origin_id in $inputIds and account.status.purge_ind is missing",
        "select meta().id from %{bucket} where rel_id in $inputIds and account.status.purge_ind is missing",
        "select meta().id from %{bucket} where account.identifiers.alt_acct_id in $inputIds and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where @levelId in $inputIds and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where @levelId in $levelIds and account.status.purge_ind is missing",
        "select meta().id from %{bucket} where account.typ.ctgy_typ_cd in ['MCA', 'BCA'] and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} use keys $inputIds where account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in customer.profiles satisfies [v.id, v.typ] = [$inputId, 'KABBAGE_PERSON_IDENTIFIER'] end and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in customer.profiles satisfies [v.id, v.typ] = [$inputId, 'FIS_BUSINESS_IDENTIFIER'] end and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in customer.profiles satisfies [v.id, v.typ] = [$inputId, 'FIS_CUSTOMER_IDENTIFIER'] end and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in customer.profiles satisfies [v.id, v.typ] = [$inputId, 'MBP_FIS_CUSTOMER_IDENTIFIER'] end and account.status.purge_ind is missing",
        "select meta().id as outputIds from %{bucket} where any v in customer.profiles satisfies [v.id, v.typ] = [$inputId, 'DIGITAL_PROFILE_IDENTIFIER'] end and account.status.purge_ind is missing",
        "CREATE PRIMARY INDEX ON DataCacheStore.C360.Customer",
        "CREATE PRIMARY INDEX ON DataCacheStore.C360.Account",
        "DELETE FROM DataCacheStore.C360.Customer",
        "DELETE FROM DataCacheStore.C360.Account",
        "select meta().id as id from DataCacheStore.C360.Customer",
        "select meta().id as id from DataCacheStore.C360.Account"
      ],
      "replicaSet": "",
      "schemaName": "",
      "serverHost": "couchbaseContainer.getConnectionString(), unknown"
    },
    {
      "databaseName": "rtfdb",
      "bucketName": "",
      "clusterName": "e3_ipc1,e3_ipc2,unknown, e3_ipc1,e3_ipc2",
      "databaseType": "PostgreSQL",
      "entities": [],
      "queries": [],
      "replicaSet": "",
      "schemaName": "public",
      "serverHost": "unknown, unknown,unknown"
    },
    {
      "databaseName": "identitystoredb",
      "bucketName": "unknown",
      "clusterName": "unknown",
      "databaseType": "PostgreSQL",
      "entities": [],
      "queries": [],
      "replicaSet": "unknown",
      "schemaName": "unknown",
      "serverHost": "unknown"
    },
    {
      "databaseName": "identitystore",
      "bucketName": "",
      "clusterName": "",
      "databaseType": "PostgreSQL",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id_store_row_key_id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "identity_doc_tx",
              "datatype": "string"
            }
          ],
          "table_name": "identity_store"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id_store_row_key_id",
              "datatype": "uuid"
            },
            {
              "CRUD": "read",
              "column_name": "identity_doc_tx",
              "datatype": "jsonb"
            },
            {
              "CRUD": "read",
              "column_name": "acctId",
              "datatype": "text"
            },
            {
              "CRUD": "read",
              "column_name": "levelId",
              "datatype": "text"
            },
            {
              "CRUD": "read",
              "column_name": "parentAcct",
              "datatype": "text"
            },
            {
              "CRUD": "read",
              "column_name": "idType",
              "datatype": "text"
            },
            {
              "CRUD": "read",
              "column_name": "altAcctId",
              "datatype": "text"
            },
            {
              "CRUD": "read",
              "column_name": "purgeInd",
              "datatype": "boolean"
            },
            {
              "CRUD": "read",
              "column_name": "rel_id",
              "datatype": "text"
            }
          ],
          "table_name": "identity_store"
        }
      ],
      "queries": [
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE id_store_row_key_id IN ${id}",
        "SELECT identity_doc_tx FROM identitystore.identity_store WHERE id_store_row_key_id IN ($1, $2, ...)",
        "WITH temp as (SELECT DISTINCT unnest(array[${acctId}, ${levelId}]) as accts FROM identitystore.identity_store WHERE ${acctId} IN ${id}) SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${acctId} IN (SELECT accts from temp) UNION SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${levelId} IN (SELECT accts from temp)",
        "WITH temp as (SELECT DISTINCT unnest(array[${acctId}, ${parentAcct}]) as accts FROM identitystore.identity_store WHERE ${idType} IN ${id}) SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${acctId} IN (SELECT accts from temp) UNION SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${parentAcct} IN (SELECT accts from temp)",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${idType} = $1",
        "WITH temp as (SELECT DISTINCT unnest(array[${parentAcct}, ${acctId}]) as accts FROM identitystore.identity_store WHERE ${altAcctId}=$1 AND ${purgeInd} IS NULL) SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ARRAY[${acctId}, ${parentAcct}] && ARRAY(SELECT accts FROM temp)",
        "WITH temp as (SELECT ${levelId} as levelId FROM identitystore.identity_store WHERE ${idType} = $1 AND ${purgeInd} IS NULL) (SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${levelId} IN (SELECT levelId FROM temp))",
        "WITH temp as (SELECT ${levelId} as levelId FROM identitystore.identity_store WHERE id_store_row_key_id IN ${id}) (SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${levelId} IN (SELECT levelId FROM temp))",
        "WITH temp as (SELECT ${levelId} as levelId FROM identitystore.identity_store WHERE ${idType}=$1) (SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${levelId} IN (SELECT levelId FROM temp))",
        "WITH temp as (SELECT ${levelId} as levelId FROM identitystore.identity_store WHERE ${idType} = $1) (SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${levelId} IN (SELECT levelId FROM temp) AND identity_doc_tx->'account'->'typ'->>'ctgy_typ_cd' IN ('MCA', 'BCA'))",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${idType} IN ${id}",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${altAcctId} IN ${id} AND ${purgeInd} IS NULL",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE ${altAcctId} = $1 AND ${purgeInd} IS NULL",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE identity_doc_tx #> '{customer, profiles}' @> ('[{\"id\": \"' || $1 || '\", \"typ\": \"${typeOfId}\"}]')::jsonb AND ${purgeInd} IS NULL",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE identity_doc_tx->>'id' = '12345'",
        "SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE identity_doc_tx->>'rel_id' IN ${id}",
        "WITH temp as (SELECT identity_doc_tx->'customer'->>'id' as levelId FROM identitystore.identity_store WHERE id_store_row_key_id IN ${id}) (SELECT id_store_row_key_id as \"rowId\" FROM identitystore.identity_store WHERE identity_doc_tx->'customer'->>'id' IN (SELECT levelId FROM temp))"
      ],
      "replicaSet": "",
      "schemaName": "identitystore,identity_store, identitystore",
      "serverHost": "unknown, "
    },
    {
      "databaseName": "rtf",
      "bucketName": "",
      "clusterName": "",
      "databaseType": "PostgreSQL",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "write",
              "column_name": "event_id",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "row_key_tx",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "amex_correlation_id",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "header_tx",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "payload_tx",
              "datatype": "string"
            },
            {
              "CRUD": "write",
              "column_name": "create_ts",
              "datatype": "timestamp"
            },
            {
              "CRUD": "write",
              "column_name": "publish_status_cd",
              "datatype": "string"
            }
          ],
          "table_name": "rtf_event"
        },
        {
          "columns": [
            {
              "CRUD": "write,update",
              "column_name": "event_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "write",
              "column_name": "row_key_tx",
              "datatype": "unknown"
            },
            {
              "CRUD": "write",
              "column_name": "amex_correlation_id",
              "datatype": "unknown"
            },
            {
              "CRUD": "write,update",
              "column_name": "header_tx",
              "datatype": "unknown"
            },
            {
              "CRUD": "write,update",
              "column_name": "payload_tx",
              "datatype": "unknown"
            },
            {
              "CRUD": "write",
              "column_name": "create_ts",
              "datatype": "unknown"
            },
            {
              "CRUD": "update",
              "column_name": "publish_status_cd",
              "datatype": "unknown"
            }
          ],
          "table_name": "rtf.rtf_event"
        }
      ],
      "queries": [
        "INSERT INTO rtf.rtf_event(event_id,row_key_tx,amex_correlation_id,header_tx,payload_tx,create_ts) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT (event_id,create_ts) DO UPDATE SET header_tx=$7, payload_tx=$8 WHERE rtf.rtf_event.event_id=$9 AND rtf.rtf_event.create_ts=$10 RETURNING event_id",
        "UPDATE rtf.rtf_event SET publish_status_cd=$1 WHERE event_id=$2 AND create_ts=$3"
      ],
      "replicaSet": "",
      "schemaName": "rtf",
      "serverHost": "unknown"
    },
    {
      "databaseName": "DATA_CACHE_STORE_BUCKET",
      "bucketName": "DATA_CACHE_STORE_BUCKET",
      "clusterName": "",
      "databaseType": "unknown",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "read,write,delete",
              "column_name": "key",
              "datatype": "string"
            }
          ],
          "table_name": "DATA_CACHE_STORE_BUCKET"
        }
      ],
      "queries": [
        "getByKey",
        "bulkGetByKeys",
        "deleteByKey",
        "insertByKey",
        "replaceByKey"
      ],
      "replicaSet": "",
      "schemaName": "unknown",
      "serverHost": ""
    },
    {
      "databaseName": "EntityStore_Hiped",
      "bucketName": "EntityStore_Hiped",
      "clusterName": "ENTITYSTORE, unknown",
      "databaseType": "COUCHBASE",
      "entities": [
        {
          "columns": [
            {
              "CRUD": "delete",
              "column_name": "id",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped._default._default"
        },
        {
          "columns": [
            {
              "CRUD": "delete,read",
              "column_name": "id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "ultimate_parent_identifier",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped.LegalEntity.Active"
        },
        {
          "columns": [
            {
              "CRUD": "delete,read",
              "column_name": "id",
              "datatype": "string"
            },
            {
              "CRUD": "read",
              "column_name": "ultimate_parent_identifier",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped.CounterpartyEntity.Active"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "id",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped.LegalEntity.Active"
        },
        {
          "columns": [
            {
              "CRUD": "read",
              "column_name": "meta().id",
              "datatype": "string"
            }
          ],
          "table_name": "EntityStore_Hiped.CounterpartyEntity.Active"
        }
      ],
      "queries": [
        "DELETE FROM EntityStore_Hiped._default._default",
        "DELETE FROM EntityStore_Hiped.LegalEntity.Active",
        "DELETE FROM EntityStore_Hiped.CounterpartyEntity.Active",
        "select meta().id as id from default:EntityStore_Hiped.LegalEntity.Active union all select meta().id as id from default:EntityStore_Hiped.CounterpartyEntity.Active union all select meta().id as id from EntityStore_Hiped",
        "ultimate_parent_identifier = $ultimateParentIdentifier limit 1",
        "select meta().id as id from EntityStore_Hiped.CounterpartyEntity.Active where ultimate_parent_identifier = $ultimate_parent_identifier",
        "DELETE FROM EntityStore_Hiped",
        "select meta().id as id from EntityStore_Hiped",
        "select meta().id as id from EntityStore_Hiped.LegalEntity.Active",
        "select meta().id as id from EntityStore_Hiped.CounterpartyEntity.Active"
      ],
      "serverHost": "couchbaseContainer.getConnectionString(), unknown",
      "replicaSet": "",
      "schemaName": ""
    },
    {
      "databaseName": "eventlogdb",
      "bucketName": "",
      "clusterName": "",
      "databaseType": "PostgreSQL",
      "entities": [],
      "queries": [],
      "replicaSet": "",
      "schemaName": "",
      "serverHost": "postgresContainer.getHost()"
    }
  ]
}

    # Generate diagram from hardcoded payload
    try:
        diagram = generate_mermaid_from_json_payload(json_payload)
        print(diagram)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def quick_generate(spec_file: str, app_id: str = None) -> str:
    """Quick one-liner to generate diagram from file"""
    return generate_mermaid_from_spec(spec_file, application_id=app_id)

def quick_generate_from_payload(json_payload: Dict, app_id: str = None) -> str:
    """Quick one-liner to generate diagram from JSON payload"""
    return generate_mermaid_from_json_payload(json_payload, application_id=app_id)

if __name__ == "__main__":
    main()
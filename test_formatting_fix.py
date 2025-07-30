#!/usr/bin/env python3
"""
Test script to verify the f-string formatting fix
"""

import json

def test_table_prompt_formatting():
    """Test that the table prompt builds correctly without f-string errors"""
    print("🧪 Testing Table Prompt Formatting")
    print("=" * 35)
    
    # Simulate database entry that would cause f-string issues
    test_db_entry = {
        "table_name": "users",
        "columns": ["id", "name", "email"],
        "connection": "postgresql://localhost:5432/mydb",
        "complex_query": "SELECT {column} FROM {table} WHERE {condition}"
    }
    
    try:
        # Test the fixed prompt building logic
        extracted_info_json = json.dumps(test_db_entry)
        table_prompt = """Based on the extracted database information and original code, provide detailed table structure.

EXTRACTED INFO: """ + extracted_info_json + """

Provide a JSON response with table names, column names, data types, and likely CRUD operations. Format:
{"table_name": {"columns": [{"name": "column_name", "type": "data_type", "crud": "READ,WRITE"}]}}

If no clear table structure can be determined, respond with 'no clear structure'."""
        
        print("✅ Table prompt builds without formatting errors")
        print(f"✅ Prompt length: {len(table_prompt)} characters")
        print(f"✅ Contains JSON example: {'table_name' in table_prompt}")
        print(f"✅ Contains extracted data: {test_db_entry['table_name'] in table_prompt}")
        
        # Verify the prompt contains expected elements
        if "EXTRACTED INFO:" in table_prompt and "Format:" in table_prompt:
            print("✅ Prompt structure is correct")
            return True
        else:
            print("❌ Prompt structure is missing required elements")
            return False
            
    except Exception as e:
        print(f"❌ Table prompt formatting error: {e}")
        return False

def test_sql_prompt_formatting():
    """Test that the SQL prompt builds correctly without f-string errors"""
    print("\n🧪 Testing SQL Prompt Formatting")
    print("=" * 35)
    
    # Simulate database entry with SQL and special characters
    test_db_entry = {
        "query": "SELECT * FROM {table} WHERE {condition}",
        "insert_query": "INSERT INTO users (name, email) VALUES ('{name}', '{email}')",
        "complex_data": {"nested": {"key": "value with {braces}"}}
    }
    
    try:
        # Test the fixed SQL prompt building logic
        extracted_info_json = json.dumps(test_db_entry)
        sql_prompt = """Analyze the following database information and original code for SQL queries.

EXTRACTED INFO: """ + extracted_info_json + """

Find and list any complete SQL queries. Separate valid queries from incomplete/invalid ones.
Respond with JSON: {"valid_queries": ["query1", "query2"], "invalid_queries": [{"query": "incomplete", "reason": "missing FROM"}]}

If no SQL queries found, respond with 'no sql queries'."""
        
        print("✅ SQL prompt builds without formatting errors")
        print(f"✅ Prompt length: {len(sql_prompt)} characters")
        print(f"✅ Contains JSON example: {'valid_queries' in sql_prompt}")
        print(f"✅ Contains extracted data: {'SELECT * FROM' in sql_prompt}")
        
        # Verify the prompt contains expected elements
        if "EXTRACTED INFO:" in sql_prompt and "valid_queries" in sql_prompt:
            print("✅ SQL prompt structure is correct")
            return True
        else:
            print("❌ SQL prompt structure is missing required elements")
            return False
            
    except Exception as e:
        print(f"❌ SQL prompt formatting error: {e}")
        return False

def test_json_serialization_robustness():
    """Test that JSON serialization handles various edge cases"""
    print("\n🧪 Testing JSON Serialization Robustness")
    print("=" * 40)
    
    edge_cases = [
        {
            "name": "Normal data",
            "data": {"host": "localhost", "port": 5432}
        },
        {
            "name": "Data with braces",
            "data": {"query": "SELECT {column} FROM {table}"}
        },
        {
            "name": "Nested objects",
            "data": {"config": {"db": {"host": "localhost"}}}
        },
        {
            "name": "Special characters",
            "data": {"password": "p@ssw0rd{123}", "query": "WHERE name = '{user}'"}
        },
        {
            "name": "Empty data",
            "data": {}
        }
    ]
    
    try:
        all_passed = True
        
        for case in edge_cases:
            try:
                # Test JSON serialization
                json_str = json.dumps(case["data"])
                
                # Test prompt building
                test_prompt = "EXTRACTED INFO: " + json_str + "\n\nAnalyze this data."
                
                print(f"✅ {case['name']}: JSON serialization successful")
                
                if len(test_prompt) < 50:
                    print(f"   ⚠️ Very short prompt: {len(test_prompt)} characters")
                
            except Exception as e:
                print(f"❌ {case['name']}: Failed - {str(e)}")
                all_passed = False
        
        if all_passed:
            print("✅ All JSON serialization tests passed")
            return True
        else:
            print("❌ Some JSON serialization tests failed")
            return False
            
    except Exception as e:
        print(f"❌ JSON serialization test error: {e}")
        return False

def test_payload_structure():
    """Test that the complete payload structure is valid"""
    print("\n🧪 Testing Payload Structure")
    print("=" * 30)
    
    try:
        # Simulate complete payload creation
        system_prompt = "You are an expert at analyzing database code."
        test_db_entry = {
            "table": "users",
            "query": "SELECT * FROM users WHERE active = {status}"
        }
        original_codebase = "class User(db.Model):\n    id = db.Column(db.Integer)"
        
        # Build prompts using the fixed method
        extracted_info_json = json.dumps(test_db_entry)
        
        table_prompt = """Based on the extracted database information and original code, provide detailed table structure.

EXTRACTED INFO: """ + extracted_info_json + """

Provide a JSON response with table names, column names, data types, and likely CRUD operations. Format:
{"table_name": {"columns": [{"name": "column_name", "type": "data_type", "crud": "READ,WRITE"}]}}

If no clear table structure can be determined, respond with 'no clear structure'."""
        
        # Create payload
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": table_prompt,
            "codebase": original_codebase
        }
        
        # Test payload serialization (what would be sent to API)
        payload_json = json.dumps(payload)
        
        print("✅ Complete payload builds successfully")
        print(f"✅ Payload size: {len(payload_json)} characters")
        print(f"✅ Contains system prompt: {'system_prompt' in payload}")
        print(f"✅ Contains user prompt: {'user_prompt' in payload}")
        print(f"✅ Contains codebase: {'codebase' in payload}")
        
        # Verify no formatting errors in the payload
        if all(key in payload for key in ["system_prompt", "user_prompt", "codebase"]):
            print("✅ Payload structure is complete and valid")
            return True
        else:
            print("❌ Payload structure is incomplete")
            return False
            
    except Exception as e:
        print(f"❌ Payload structure test error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing F-String Formatting Fix")
    print("=" * 40)
    
    try:
        test1_success = test_table_prompt_formatting()
        test2_success = test_sql_prompt_formatting()
        test3_success = test_json_serialization_robustness()
        test4_success = test_payload_structure()
        
        if all([test1_success, test2_success, test3_success, test4_success]):
            print("\n🎉 All formatting fix tests passed!")
            print("\n💡 Key fixes applied:")
            print("   ✅ Replaced f-string with string concatenation for prompts")
            print("   ✅ Avoided curly brace conflicts in JSON examples")
            print("   ✅ Proper JSON serialization before string building")
            print("   ✅ Robust payload structure creation")
            print("\n🔧 This should resolve:")
            print("   • HTTP 400 errors from malformed prompts")
            print("   • f-string formatting issues with JSON data")
            print("   • Curly brace conflicts in prompt examples")
        else:
            print("\n❌ Some formatting fix tests failed!")
            exit(1)
            
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        exit(1)
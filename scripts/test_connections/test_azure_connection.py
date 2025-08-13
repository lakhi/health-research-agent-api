#!/usr/bin/env python3
"""
Simple script to test Azure PostgreSQL connection
"""

def test_azure_connection():
    try:
        import psycopg2
        print("📦 psycopg2 imported successfully")
    except ImportError:
        print("❌ psycopg2 not found. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "psycopg2-binary"])
        import psycopg2
        print("✅ psycopg2 installed and imported")

    # Connection parameters
    connection_params = {
        "user": "postgres",
        "password": "@rP3Jx8z2M5#.Ff",
        "host": "azure-db-hrn.postgres.database.azure.com",
        "port": 5432,
        "database": "postgres",
        "sslmode": "require"  # Azure PostgreSQL requires SSL
    }
    
    print("\n🔗 Testing Azure PostgreSQL connection...")
    print(f"Host: {connection_params['host']}")
    print(f"User: {connection_params['user']}")
    print(f"Database: {connection_params['database']}")
    print(f"SSL Mode: {connection_params['sslmode']}")
    
    try:
        # Establish connection
        cnx = psycopg2.connect(**connection_params)
        print("✅ Connection established successfully!")
        
        # Test query
        cursor = cnx.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"📊 PostgreSQL Version: {version}")
        
        # Test vector extension availability
        cursor.execute("SELECT name FROM pg_available_extensions WHERE name = 'vector';")
        vector_ext = cursor.fetchone()
        if vector_ext:
            print("🧮 Vector extension is available")
        else:
            print("⚠️  Vector extension not found")
        
        # Clean up
        cursor.close()
        cnx.close()
        print("🔐 Connection closed successfully")
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Connection failed: {e}")
        print(f"Error code: {e.pgcode}")
        print(f"Error details: {e.pgerror}")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Azure PostgreSQL Connection Test")
    print("=" * 50)
    
    success = test_azure_connection()
    
    if success:
        print("\n🎉 Connection test PASSED!")
    else:
        print("\n💥 Connection test FAILED!")
        print("\n🔍 Troubleshooting steps:")
        print("1. Check if your IP is allowed in Azure PostgreSQL firewall")
        print("2. Verify the password is correct")
        print("3. Ensure SSL is enabled (Azure requires it)")
        print("4. Check if the server is running")
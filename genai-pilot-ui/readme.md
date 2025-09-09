Query 1 - Core Operations:
couchbase bucket collection document n1ql query

Query 2 - Connection/Setup:
couchbase cluster connection environment configuration

Query 3 - CRUD Operations:
bucket.get bucket.upsert bucket.insert bucket.remove collection.query

Query 4 - SDK Classes:
CouchbaseCluster CouchbaseEnvironment Bucket Collection QueryResult

Testing Strategy:

1. Run each query separately with same parameters (count: 20, threshold: 0.4)
2. Collect unique files from all results
3. Compare total coverage vs. one long query
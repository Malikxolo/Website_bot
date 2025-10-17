from neo4j import GraphDatabase, TRUST_SYSTEM_CA_SIGNED_CERTIFICATES

uri = "neo4j+s://d38aa5ae.databases.neo4j.io"
auth = ("neo4j", "U5vx6SgcFYEAH-127mkObK41aBqKglDOBvSxssw-b3I")

driver = GraphDatabase.driver(
uri,
auth=auth,
# encrypted=True,
# trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
)
driver.verify_connectivity()
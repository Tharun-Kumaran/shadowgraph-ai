// ShadowGraph AI — uniqueness constraints (Neo4j 5.x Community).
// Every graph entity carries the SGNode label and a stable `uid`.
// Idempotent: safe to run repeatedly.
CREATE CONSTRAINT sgnode_uid IF NOT EXISTS FOR (n:SGNode) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT handle_uid IF NOT EXISTS FOR (n:Handle) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT post_uid IF NOT EXISTS FOR (n:Post) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT source_uid IF NOT EXISTS FOR (n:Source) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT indicator_uid IF NOT EXISTS FOR (n:Indicator) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT cve_uid IF NOT EXISTS FOR (n:CVE) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT malware_uid IF NOT EXISTS FOR (n:Malware) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT organization_uid IF NOT EXISTS FOR (n:Organization) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT product_uid IF NOT EXISTS FOR (n:Product) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT incident_uid IF NOT EXISTS FOR (n:Incident) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT evidence_uid IF NOT EXISTS FOR (n:Evidence) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT audit_uid IF NOT EXISTS FOR (n:AuditEvent) REQUIRE n.uid IS UNIQUE;

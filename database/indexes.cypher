// ShadowGraph AI — secondary indexes. Idempotent.
CREATE INDEX sgnode_type IF NOT EXISTS FOR (n:SGNode) ON (n.type);
CREATE INDEX sgnode_value IF NOT EXISTS FOR (n:SGNode) ON (n.value);
CREATE INDEX handle_name IF NOT EXISTS FOR (n:Handle) ON (n.name);
CREATE INDEX post_hash IF NOT EXISTS FOR (n:Post) ON (n.content_hash);
CREATE INDEX post_observed IF NOT EXISTS FOR (n:Post) ON (n.observed_at);
CREATE INDEX indicator_type IF NOT EXISTS FOR (n:Indicator) ON (n.type);
CREATE INDEX audit_target IF NOT EXISTS FOR (n:AuditEvent) ON (n.target_id);
CREATE INDEX same_as_clue IF NOT EXISTS FOR ()-[r:SAME_AS]-() ON (r.clue_id);
CREATE INDEX same_as_status IF NOT EXISTS FOR ()-[r:SAME_AS]-() ON (r.status);
CREATE FULLTEXT INDEX post_text IF NOT EXISTS FOR (n:Post) ON EACH [n.text];

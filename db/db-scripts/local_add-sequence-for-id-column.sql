CREATE SEQUENCE IF NOT EXISTS ai.research_papers_id_seq;
ALTER TABLE ai.research_papers 
ALTER COLUMN id SET DEFAULT nextval('ai.research_papers_id_seq');

-- Migration: Add conversation and file_tree fields to GenerationSession
-- This adds support for the agentic workflow with conversation history

-- Add file_tree JSON field for hierarchical folder structure
ALTER TABLE builder_generationsession 
ADD COLUMN IF NOT EXISTS file_tree JSONB DEFAULT '{}'::jsonb;

-- Add conversation JSON field for agentic workflow chat history  
ALTER TABLE builder_generationsession 
ADD COLUMN IF NOT EXISTS conversation JSONB DEFAULT '[]'::jsonb;

-- Add version field for version control
ALTER TABLE builder_generationsession 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- Add parent_session foreign key for branching/versioning
ALTER TABLE builder_generationsession 
ADD COLUMN IF NOT EXISTS parent_session_id UUID REFERENCES builder_generationsession(id) ON DELETE SET NULL;

-- Create index for faster parent_session queries
CREATE INDEX IF NOT EXISTS idx_builder_generationsession_parent 
ON builder_generationsession(parent_session_id);

-- Create index for faster user conversation queries
CREATE INDEX IF NOT EXISTS idx_builder_generationsession_conversation 
ON builder_generationsession USING GIN (conversation);

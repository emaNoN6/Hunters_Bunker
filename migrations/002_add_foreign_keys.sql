/*
 * # ==========================================================
 * # Hunter's Command Console
 * #
 * # File: 002_add_foreign_keys.sql
 * # Last Modified: 7/27/25, 2:57 PM
 * # Copyright (c) 2025, M. Stilson & Codex
 * #
 * # This program is free software; you can redistribute it and/or modify
 * # it under the terms of the MIT License.
 * #
 * # This program is distributed in the hope that it will be useful,
 * # but WITHOUT ANY WARRANTY; without even the implied warranty of
 * # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * # LICENSE file for more details.
 * # ==========================================================
 */

-- =======================================================
-- Hunter's Almanac: Migration 002
-- This script adds all foreign key constraints to the
-- database, creating the relational links between tables
-- and enforcing data integrity.
-- =======================================================

-- Link the acquisition log back to the source that found the item.
ALTER TABLE public.acquisition_log
ADD CONSTRAINT fk_acquisition_log_source
FOREIGN KEY (source_id) REFERENCES public.sources(id)
ON DELETE RESTRICT; -- Prevents deleting a source if it has log entries

-- Link media evidence back to its parent case.
ALTER TABLE public.media_evidence
ADD CONSTRAINT fk_media_evidence_case
FOREIGN KEY (case_id) REFERENCES public.cases(id)
ON DELETE CASCADE; -- If a case is deleted, its associated media is also deleted

-- Link investigation nodes (pushpins) to their parent investigation (cork board).
ALTER TABLE public.investigation_nodes
ADD CONSTRAINT fk_investigation_nodes_investigation
FOREIGN KEY (investigation_id) REFERENCES public.investigations(id)
ON DELETE CASCADE; -- If an investigation is deleted, all its nodes are deleted

-- Link investigation links (red string) to their parent investigation.
ALTER TABLE public.investigation_links
ADD CONSTRAINT fk_investigation_links_investigation
FOREIGN KEY (investigation_id) REFERENCES public.investigations(id)
ON DELETE CASCADE; -- If an investigation is deleted, all its links are deleted

-- Link the start of a string to a specific pushpin.
ALTER TABLE public.investigation_links
ADD CONSTRAINT fk_investigation_links_node_a
FOREIGN KEY (node_a_id) REFERENCES public.investigation_nodes(id)
ON DELETE CASCADE;

-- Link the end of a string to a specific pushpin.
ALTER TABLE public.investigation_links
ADD CONSTRAINT fk_investigation_links_node_b
FOREIGN KEY (node_b_id) REFERENCES public.investigation_nodes(id)
ON DELETE CASCADE;


# Tasks: PDF Document RAG Search System

**Input**: Design documents from `/specs/001-pdf-rag-search/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - tests are optional and not included in this task list.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths based on plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure per plan.md (src/models/, src/services/, src/cli/, src/lib/, tests/, data/)
- [ ] T002 Initialize Python 3.11+ project with pyproject.toml and requirements.txt
- [ ] T003 [P] Add dependencies: pdfplumber, chromadb, openai, sentence-transformers, typer, rich, pydantic
- [ ] T004 [P] Configure .gitignore for Python, data/, .env files
- [ ] T005 [P] Create .env.example with OPENAI_API_KEY placeholder

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create configuration management in src/models/config.py (load from env vars and optional YAML config file)
- [ ] T007 [P] Create Document model with all fields in src/models/document.py (id, name, file_path, page_count, status, etc.)
- [ ] T008 [P] Create Chunk model with all fields in src/models/chunk.py (id, document_id, content, page_number, embedding, metadata)
- [ ] T009 [P] Create Response and Citation models in src/models/response.py (answer, citations, metadata)
- [ ] T010 Implement OpenAI client wrapper in src/lib/openai_client.py (embeddings and chat completions)
- [ ] T011 Implement ChromaDB abstraction in src/lib/vector_store.py (PersistentClient, add, query, delete)
- [ ] T012 Implement SQLite metadata store in src/lib/metadata_store.py (CRUD for Document records)
- [ ] T013 Create CLI app skeleton with Typer in src/cli/main.py (app entry point, --help)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Index PDF Documents from Folder (Priority: P1) 🎯 MVP

**Goal**: Accept a folder path and index all PDF files with progress feedback

**Independent Test**: Run `smart-rag index /path/to/pdfs` and verify documents appear in `smart-rag status`

### Implementation for User Story 1

- [ ] T014 [US1] Implement PDF text extraction in src/services/pdf_extractor.py (extract text per page including tables)
- [ ] T015 [US1] Add page iteration with flush_cache() for memory efficiency in src/services/pdf_extractor.py
- [ ] T016 [US1] Implement table extraction logic in src/services/pdf_extractor.py (pdfplumber extract_tables)
- [ ] T017 [US1] Implement LLM-assisted chunking in src/services/chunker.py (GPT-4o determines semantic boundaries)
- [ ] T018 [US1] Add chunk metadata generation in src/services/chunker.py (page_number, has_table, section_title)
- [ ] T019 [US1] Implement embedding generation for chunks in src/services/chunker.py (text-embedding-3-large)
- [ ] T020 [US1] Implement indexer service in src/services/indexer.py (orchestrate extraction → chunking → storage)
- [ ] T021 [US1] Add document status management in src/services/indexer.py (pending → processing → completed/failed)
- [ ] T022 [US1] Add progress feedback with rich progress bar in src/services/indexer.py
- [ ] T023 [US1] Implement error handling for corrupt/protected PDFs in src/services/indexer.py (skip with logging)
- [ ] T024 [US1] Implement `index` CLI command in src/cli/main.py (folder_path argument, --recursive, --force, --verbose)
- [ ] T025 [US1] Implement `status` CLI command in src/cli/main.py (show indexed docs, chunks, storage size)
- [ ] T026 [US1] Implement `clear` CLI command in src/cli/main.py (--yes flag, confirmation prompt)

**Checkpoint**: User Story 1 complete - users can now index PDFs and check status

---

## Phase 4: User Story 2 - Query Documents for Definitions (Priority: P1)

**Goal**: Answer definition questions with accurate responses and source citations

**Independent Test**: Query "What is the definition of X?" and verify answer matches source document content

**Depends on**: User Story 1 (documents must be indexed)

### Implementation for User Story 2

- [ ] T027 [US2] Implement similarity search in src/services/retriever.py (ChromaDB query, top 30+ chunks)
- [ ] T028 [US2] Implement cross-encoder reranking in src/services/retriever.py (sentence-transformers ms-marco model)
- [ ] T029 [US2] Add relevance score calculation in src/services/retriever.py (normalize reranker scores)
- [ ] T030 [US2] Implement grounded response generation in src/services/generator.py (GPT-4o with retrieved context)
- [ ] T031 [US2] Add citation extraction in src/services/generator.py (document_name, page_number, verbatim_quote)
- [ ] T032 [US2] Implement "not found" detection in src/services/generator.py (return clear message when no relevant info)
- [ ] T033 [US2] Implement `query` CLI command in src/cli/main.py (question argument, --json, --max-sources)
- [ ] T034 [US2] Add human-readable output formatting in src/cli/main.py (answer, sources with quotes, metadata)
- [ ] T035 [US2] Add JSON output formatting in src/cli/main.py (structured response per CLI contract)

**Checkpoint**: User Story 2 complete - users can query for definitions with citations

---

## Phase 5: User Story 3 - Query Documents for Entity Information (Priority: P1)

**Goal**: Answer "who" and "what" questions with complete aggregated lists from multiple sources

**Independent Test**: Query "Who are the X?" and verify all matching entities from all documents are listed

**Depends on**: User Story 2 (retriever and generator must exist)

### Implementation for User Story 3

- [ ] T036 [US3] Enhance retriever to gather from multiple documents in src/services/retriever.py (deduplicate by document)
- [ ] T037 [US3] Enhance generator prompt for list aggregation in src/services/generator.py (synthesize across sources)
- [ ] T038 [US3] Add multi-source citation grouping in src/services/generator.py (each item cites its source)

**Checkpoint**: User Story 3 complete - entity queries return complete aggregated lists

---

## Phase 6: User Story 4 - Fast Query Response (Priority: P2)

**Goal**: Ensure query responses return within 30 seconds

**Independent Test**: Time query responses and verify they complete under 30 seconds

**Depends on**: User Stories 2 & 3 (query pipeline must exist)

### Implementation for User Story 4

- [ ] T039 [US4] Add timing instrumentation in src/services/retriever.py and src/services/generator.py
- [ ] T040 [US4] Optimize embedding batch processing in src/services/chunker.py (batch API calls)
- [ ] T041 [US4] Add caching for reranker model loading in src/services/retriever.py (load once, reuse)
- [ ] T042 [US4] Display response time in CLI output in src/cli/main.py

**Checkpoint**: User Story 4 complete - queries return within target time

---

## Phase 7: User Story 5 - Grounded and Verifiable Responses (Priority: P2)

**Goal**: Ensure all responses are grounded in document content with verifiable citations

**Independent Test**: Compare response claims against cited source documents

**Depends on**: User Stories 2 & 3 (citation system must exist)

### Implementation for User Story 5

- [ ] T043 [US5] Enhance generator prompt to enforce grounding in src/services/generator.py (only use retrieved content)
- [ ] T044 [US5] Add verbatim quote extraction validation in src/services/generator.py (verify quotes exist in chunks)
- [ ] T045 [US5] Implement confidence scoring in src/services/generator.py (based on reranker scores)
- [ ] T046 [US5] Add --no-quotes CLI option in src/cli/main.py (omit verbatim quotes for compact output)

**Checkpoint**: User Story 5 complete - all responses are fully grounded and verifiable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T047 [P] Add comprehensive error messages per CLI contract in src/cli/main.py
- [ ] T048 [P] Add logging configuration in src/models/config.py (configurable log level)
- [ ] T049 [P] Create sample PDF fixtures in tests/fixtures/sample_pdfs/ for manual testing
- [ ] T050 Validate all CLI commands against contracts/cli-interface.md
- [ ] T051 Validate quickstart.md workflow end-to-end
- [ ] T052 [P] Add README.md with installation and usage instructions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - MVP indexing capability
- **User Story 2 (Phase 4)**: Depends on US1 (must have indexed documents)
- **User Story 3 (Phase 5)**: Depends on US2 (uses retriever/generator)
- **User Story 4 (Phase 6)**: Depends on US2 & US3 (optimizes query pipeline)
- **User Story 5 (Phase 7)**: Depends on US2 & US3 (enhances grounding)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

```
US1 (Index) ─────┐
                 ├──► US2 (Definitions) ───┬──► US4 (Speed)
                 │                         │
                 └──────────────────────────┼──► US3 (Entities) ──► US5 (Grounding)
```

- **User Story 1 (P1)**: Independent - foundational capability
- **User Story 2 (P1)**: Requires US1 (needs indexed documents)
- **User Story 3 (P1)**: Requires US2 (extends query capability)
- **User Story 4 (P2)**: Requires US2/US3 (optimizes existing query)
- **User Story 5 (P2)**: Requires US2/US3 (enhances existing citation)

### Parallel Opportunities

Within Phase 2 (Foundational):
- T007, T008, T009 can run in parallel (different model files)

Within Phase 3 (US1):
- T014-T016 (extraction) can proceed while T017-T019 (chunking) are designed

Within Phase 8 (Polish):
- T047, T048, T049, T052 can all run in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all model files together:
Task: "Create Document model in src/models/document.py"
Task: "Create Chunk model in src/models/chunk.py"
Task: "Create Response and Citation models in src/models/response.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `smart-rag index` and `smart-rag status`
5. Proceed to User Story 2 for query capability

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test indexing → **MVP: Can index PDFs**
3. Add User Story 2 → Test definition queries → **Can query for definitions**
4. Add User Story 3 → Test entity queries → **Can query for entities**
5. Add User Stories 4 & 5 → Optimize and harden → **Production-ready**

### Suggested MVP Scope

**Phase 1 + Phase 2 + Phase 3 (User Story 1)**: Minimum to demonstrate indexing capability

**Phase 1 + Phase 2 + Phase 3 + Phase 4 (User Stories 1 & 2)**: Minimum useful product (can actually answer questions)

---

## Summary

| Phase | Tasks | Parallel Tasks | Description |
|-------|-------|----------------|-------------|
| Phase 1: Setup | 5 | 3 | Project initialization |
| Phase 2: Foundational | 8 | 3 | Core infrastructure |
| Phase 3: US1 | 13 | 0 | PDF indexing |
| Phase 4: US2 | 9 | 0 | Definition queries |
| Phase 5: US3 | 3 | 0 | Entity queries |
| Phase 6: US4 | 4 | 0 | Performance optimization |
| Phase 7: US5 | 4 | 0 | Grounding enhancement |
| Phase 8: Polish | 6 | 4 | Documentation & cleanup |
| **Total** | **52** | **10** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Edge cases (corrupt PDFs, password protection) are handled in US1 (T023)

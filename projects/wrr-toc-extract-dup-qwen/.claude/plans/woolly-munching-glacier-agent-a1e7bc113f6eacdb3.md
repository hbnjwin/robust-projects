# Plan: Eliminate Duplicated Code Between Service Classes

## Overview

Extract two duplicated private methods (processTocData and createExtractionTasks) from
DocumentsServiceImpl and DocumentOcrProcessorService into a new shared @Component, then
have both services delegate to it. Remove the dead createExtractionTasks from DocumentsServiceImpl.

---

## Pre-Implementation Analysis

### Confirmed Call Sites

| Method | Class | Called From | Status |
|---|---|---|---|
| processTocData | DocumentsServiceImpl (line 496) | regenerateToc() line 468 | Active |
| processTocData | DocumentOcrProcessorService (line 151) | processOcrAsync() line 106 | Active |
| createExtractionTasks | DocumentsServiceImpl (line 576) | NOWHERE | DEAD CODE |
| createExtractionTasks | DocumentOcrProcessorService (line 232) | processOcrAsync() line 122 | Active |

### Fields That Become Unused After Deletion

**DocumentsServiceImpl:**
- extractionTasksRepository (line 79) -- only used in dead createExtractionTasks
- extractionRulesRepository (line 82) -- only used in dead createExtractionTasks
- queryFactory (line 99) -- only used in dead createExtractionTasks
- entityManager (line 64) -- KEEP (still used in createOrUpdate and getDocumentsDetail)
- Setter setEntityManager -- KEEP but simplify (remove queryFactory init line)

**DocumentOcrProcessorService:**
- entityManager (line 40) -- only used in deleted createExtractionTasks
- queryFactory (line 57) -- only used in deleted createExtractionTasks
- Setter setEntityManager (lines 59-63) -- DELETE entirely
- extractionTasksRepository (line 49) -- only used in deleted createExtractionTasks
- extractionRulesRepository (line 52) -- only used in deleted createExtractionTasks
---

## Step 1: Create ExtractionSharedService

**Create file:** src/main/java/com/linkyoyo/reportaudit/service/impl/ExtractionSharedService.java

This is a @Component with two public methods. The method bodies are taken from the
canonical versions in DocumentOcrProcessorService (which has the more correct createExtractionTasks).

### Class skeleton:

    package com.linkyoyo.reportaudit.service.impl;

    // Imports: DocumentsToc, ExtractionTasks, ExtractionRules, RuleClass, SysOperator,
    //          QExtractionTasks, QExtractionRules, DocumentsTocRepository,
    //          ExtractionTasksRepository, RuleClassUtils, JPAQueryFactory,
    //          BooleanExpression, EntityManager, BigDecimal, LocalDateTime,
    //          List, Map, UUID, Collectors

    @Component
    public class ExtractionSharedService {

        @Autowired private DocumentsTocRepository documentsTocRepository;
        @Autowired private ExtractionTasksRepository extractionTasksRepository;
        @Autowired private EntityManager entityManager;
        private JPAQueryFactory queryFactory;

        @Autowired
        public void setEntityManager(EntityManager em) {
            this.entityManager = em;
            this.queryFactory = new JPAQueryFactory(em);
        }

        // processTocData: exact body from either class (byte-for-byte identical)
        public void processTocData(Integer docId, List<Map<String, Object>> tocList) { ... }

        // createExtractionTasks: body from DocumentOcrProcessorService (canonical version)
        public void createExtractionTasks(Long docId, SysOperator currentUser) { ... }
    }

### Canonical decisions for createExtractionTasks:

| Difference | Resolution | Reason |
|---|---|---|
| SysOperator as param vs SysUserUtils.currentUser() | Accept as parameter | More flexible |
| .orderBy(qExtractionRules.id.asc()) present/absent | Include it | Deterministic ordering |
| Commented-out CollectionUtil.sort line | Omit | Dead code should not propagate |
---

## Step 2: Modify DocumentOcrProcessorService

**File:** src/main/java/com/linkyoyo/reportaudit/service/impl/DocumentOcrProcessorService.java

### 2a. Add new field (after existing @Autowired fields)

    @Autowired
    private ExtractionSharedService extractionSharedService;

### 2b. Update call sites in processOcrAsync()

Line 106:
    BEFORE: processTocData(document.getId().intValue(), tocList);
    AFTER:  extractionSharedService.processTocData(document.getId().intValue(), tocList);

Line 122:
    BEFORE: createExtractionTasks(document.getId().longValue(), currentUser);
    AFTER:  extractionSharedService.createExtractionTasks(document.getId().longValue(), currentUser);

### 2c. Delete fields no longer used

- Lines 39-40: EntityManager entityManager -- DELETE
- Lines 46-47: DocumentsTocRepository -- DELETE
- Lines 49-50: ExtractionTasksRepository -- DELETE
- Lines 52-53: ExtractionRulesRepository -- DELETE
- Line 57: JPAQueryFactory queryFactory -- DELETE
- Lines 59-63: setEntityManager() setter -- DELETE entirely

KEEP: DocumentsRepository, TextinService (both used in processOcrAsync)

### 2d. Delete the two private methods

- Delete lines 145-222: processTocData() and Javadoc
- Delete lines 224-317: createExtractionTasks() and Javadoc

### 2e. Remove unused imports (15 imports)

- cn.hutool.core.collection.CollectionUtil
- com.linkyoyo.reportaudit.entity.DocumentsToc
- com.linkyoyo.reportaudit.entity.ExtractionTasks
- com.linkyoyo.reportaudit.entity.ExtractionRules
- com.linkyoyo.reportaudit.entity.RuleClass
- com.linkyoyo.reportaudit.repository.DocumentsTocRepository
- com.linkyoyo.reportaudit.repository.ExtractionTasksRepository
- com.linkyoyo.reportaudit.repository.ExtractionRulesRepository
- com.linkyoyo.reportaudit.util.RuleClassUtils
- com.querydsl.jpa.impl.JPAQueryFactory
- com.linkyoyo.reportaudit.entity.QExtractionTasks
- com.linkyoyo.reportaudit.entity.QExtractionRules
- java.math.BigDecimal
- java.util.UUID
- java.util.stream.Collectors

### Resulting file (~140 lines, down from 318)

    @Service
    public class DocumentOcrProcessorService {
        @Autowired private DocumentsRepository documentsRepository;
        @Autowired private TextinService textinService;
        @Autowired private ExtractionSharedService extractionSharedService;

        @Async
        public void processOcrAsync(File originalFile, Integer documentId, SysOperator currentUser) {
            // body unchanged except two delegated calls
        }
    }
---

## Step 3: Modify DocumentsServiceImpl

**File:** src/main/java/com/linkyoyo/reportaudit/service/impl/DocumentsServiceImpl.java

### 3a. Add new field (near existing @Autowired fields)

    @Autowired
    private ExtractionSharedService extractionSharedService;

### 3b. Update call site in regenerateToc()

Line 468:
    BEFORE: processTocData(docId, tocList);
    AFTER:  extractionSharedService.processTocData(docId, tocList);

### 3c. Delete BOTH private methods

- Delete lines 490-567: processTocData() and Javadoc
- Delete lines 569-661: createExtractionTasks() and Javadoc (DEAD CODE, no callers)

### 3d. Delete fields no longer used

- Lines 79-80: ExtractionTasksRepository -- DELETE
- Lines 82-83: ExtractionRulesRepository -- DELETE
- Line 99: JPAQueryFactory queryFactory -- DELETE

### 3e. Simplify setEntityManager setter

    BEFORE (lines 67-70):
    @Autowired
    public void setEntityManager(EntityManager entityManager) {
        this.entityManager = entityManager;
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    AFTER:
    @Autowired
    public void setEntityManager(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

### 3f. Remove unused imports (12 imports)

- com.linkyoyo.reportaudit.entity.ExtractionTasks
- com.linkyoyo.reportaudit.entity.ExtractionRules
- com.linkyoyo.reportaudit.entity.RuleClass
- com.linkyoyo.reportaudit.repository.ExtractionTasksRepository
- com.linkyoyo.reportaudit.repository.ExtractionRulesRepository
- com.linkyoyo.reportaudit.util.RuleClassUtils
- com.querydsl.jpa.impl.JPAQueryFactory
- com.linkyoyo.reportaudit.entity.QExtractionTasks
- com.linkyoyo.reportaudit.entity.QExtractionRules
- java.math.BigDecimal
- java.util.UUID
- java.util.Comparator

### Keep these imports (still used)

- DocumentsToc -- used in createOrUpdate(), getDocumentsDetail()
- DocumentsTocRepository -- used in createOrUpdate(), getDocumentsDetail(), regenerateToc()
- SysUserUtils -- used in getDocumentsList(), uploadFileWithOcr()
- EntityManager -- used in createOrUpdate(), getDocumentsDetail()
- All other existing imports

### Resulting file (~520 lines, down from 685)

All public API methods unchanged: getDocumentsList, createOrUpdate, getDocumentsDetail,
uploadFileWithOcr, regenerateToc, markDeleted, getFileType.
---

## Step 4: Verification Checklist

After making all changes, verify:

- [ ] mvn compile succeeds -- no missing imports, no unresolved symbols
- [ ] ExtractionSharedService is detected by Spring component scanning (same package)
- [ ] DocumentOcrProcessorService.processOcrAsync() delegates to extractionSharedService
- [ ] DocumentsServiceImpl.regenerateToc() delegates to extractionSharedService
- [ ] DocumentsServiceImpl no longer contains createExtractionTasks (dead code removed)
- [ ] No unused imports remain in either file
- [ ] No unused @Autowired fields remain in either file
- [ ] The shared createExtractionTasks includes .orderBy(qExtractionRules.id.asc())
- [ ] The shared createExtractionTasks accepts SysOperator currentUser as parameter

---

## File Change Summary

| File | Action | Lines Before | Lines After (approx) |
|---|---|---|---|
| service/impl/ExtractionSharedService.java | CREATE | 0 | ~155 |
| service/impl/DocumentOcrProcessorService.java | MODIFY | 318 | ~140 |
| service/impl/DocumentsServiceImpl.java | MODIFY | 685 | ~520 |
| TOTAL | | 1003 | ~815 |

Net result: ~188 fewer lines, zero duplication, one dead method removed, one bug
(missing .orderBy()) fixed as a side effect.

---

## Risk Assessment

LOW RISK. This refactoring:
- Changes no public API contracts
- Changes no business logic (the unified methods are exact copies of existing code)
- The only behavioral change is adding .orderBy(qExtractionRules.id.asc()) to the
  DocumentsServiceImpl path -- but since that method was dead code, zero runtime impact
- Spring component scanning will automatically discover the new @Component in same package
- No database schema changes, no configuration changes, no dependency changes

---

## Implementation Order

The three steps should be executed in this exact order:

1. **Create ExtractionSharedService first** -- no existing code depends on it yet, so this
   is a safe additive change that compiles immediately.

2. **Modify DocumentOcrProcessorService second** -- it has the simpler structure (fewer
   methods, fewer imports). Its two private methods become simple delegations.

3. **Modify DocumentsServiceImpl third** -- it has the most complex import cleanup and
   field removal. By this point the shared class is already proven to compile from step 2.

After each step, run mvn compile to catch issues early.

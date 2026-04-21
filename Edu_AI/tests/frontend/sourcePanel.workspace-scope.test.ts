import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(
  new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  file,
  /getKnowledgeBaseDocuments/,
  'SourcePanel should load visible files from the scoped course knowledge base',
);

assert.match(
  file,
  /const COURSE_LIBRARY_TYPE = 'course';/,
  'SourcePanel should define an explicit course library type for formal course documents',
);

assert.match(
  file,
  /const PERSONAL_LIBRARY_TYPE = 'personal';/,
  'SourcePanel should define an explicit personal library type for teacher-owned documents',
);

assert.match(
  file,
  /const shouldLoadLegacyRagDocuments = workspaceScope\?\.scopeType !== 'knowledge_point';/,
  'SourcePanel should load legacy RAG documents in course-total mode for historical compatibility',
);

assert.match(
  file,
  /shouldLoadLegacyRagDocuments \? listDocuments\(\) : Promise\.resolve\(\[\]\)/,
  'SourcePanel should still merge legacy RAG documents outside knowledge-point mode',
);

assert.match(
  file,
  /scopeType:\s*workspaceScope\?\.scopeType/,
  'SourcePanel should pass the current workspace scope type to knowledge-base requests',
);

assert.match(
  file,
  /scopeId:\s*workspaceScope\?\.scopeId/,
  'SourcePanel should pass the current workspace scope id to knowledge-base requests',
);

assert.match(
  file,
  /libraryType:\s*COURSE_LIBRARY_TYPE/,
  'SourcePanel should request formal course knowledge documents separately',
);

assert.match(
  file,
  /includeDescendants:\s*true/,
  'SourcePanel should allow parent-node course knowledge requests to include descendant nodes',
);

assert.match(
  file,
  /libraryType:\s*PERSONAL_LIBRARY_TYPE/,
  'SourcePanel should request personal knowledge documents separately',
);

assert.match(
  file,
  /includeDescendants:\s*false/,
  'SourcePanel should keep personal knowledge requests limited to the current node',
);

assert.match(
  file,
  /getKnowledgeGraph/,
  'SourcePanel should load the course knowledge graph so course documents can be rendered as a directory tree',
);

assert.match(
  file,
  /renderCourseLibraryTreeNode/,
  'SourcePanel should render course knowledge documents with a tree node renderer',
);

assert.match(
  file,
  /collectCourseFileKeysForNode/,
  'SourcePanel should collect all document ids from a non-leaf course node subtree for one-click selection',
);

assert.match(
  file,
  /handleCourseNodeSelectAll/,
  'SourcePanel should expose a dedicated handler to select or clear every document under a course subtree',
);

assert.doesNotMatch(
  file,
  /disabled=\{subtreeFileKeys\.length === 0\}/,
  'SourcePanel should keep every course directory checkbox clickable even when that node currently has zero documents',
);

assert.match(
  file,
  /indeterminate=\{subtreeIndeterminate\}/,
  'SourcePanel should show a partial-selection state when only some documents under a course subtree are checked',
);

assert.doesNotMatch(
  file,
  /showToggle \? \(\s*<Checkbox/,
  'SourcePanel should render a checkbox for leaf nodes as well, not only for non-leaf course nodes',
);

assert.match(
  file,
  /source-panel__tree-node-count">\{subtreeDocumentCount\}</,
  'SourcePanel should display the total visible document count for the whole course subtree on each tree node',
);

assert.doesNotMatch(
  file,
  /if \(nodeFiles\.length === 0 && !hasVisibleChildren\) \{\s*return null;\s*\}/,
  'SourcePanel should keep rendering the course directory tree even when a node currently has zero documents',
);

assert.match(
  file,
  /courseLibraryTreeRoot\s*\?\s*\(?\s*renderCourseLibraryTreeNode\(courseLibraryTreeRoot\)/,
  'SourcePanel should render the course knowledge tree whenever the graph exists, not only when documents are already present',
);

assert.doesNotMatch(
  file,
  /fileList\.length === 0 && !loading/,
  'SourcePanel should not replace the whole library area with a global empty state when both scoped lists are empty',
);

assert.match(
  file,
  /personalFileList\.map\(renderFileItem\)/,
  'SourcePanel should continue rendering the personal knowledge base as a flat list',
);

assert.match(
  file,
  /uploadKnowledgeBaseDocument/,
  'SourcePanel uploads should write through the knowledge-base upload API',
);

assert.match(
  file,
  /libraryType:\s*PERSONAL_LIBRARY_TYPE/,
  'SourcePanel uploads from the Q&A workspace should write to the current personal knowledge base',
);

assert.match(
  file,
  /libraryType:\s*COURSE_LIBRARY_TYPE/,
  'SourcePanel should promote personal documents into the current course knowledge base',
);

assert.match(
  file,
  /documentId:\s*doc\.id/,
  'SourcePanel should retain the original knowledge-base document id on visible file items so personal-file promotions can be traced back to their source',
);

assert.match(
  file,
  /promotedFromDocumentId:\s*file\.documentId/,
  'SourcePanel should send the original personal document id when promoting a file into the course knowledge base',
);

assert.match(
  file,
  /deleteKnowledgeBaseDocument/,
  'SourcePanel should use the course knowledge-base delete API for scoped knowledge documents',
);

assert.match(
  file,
  /await deleteKnowledgeBaseDocument\(courseId,\s*file\.documentId,\s*token\)/,
  'SourcePanel should delete course knowledge documents by their original knowledge-base document id',
);

assert.match(
  file,
  /deepSearchAndCrawl\(\{\s*query:\s*normalizedQuery,[\s\S]*course_id:\s*courseId,[\s\S]*scope_type:\s*workspaceScope\?\.scopeType,[\s\S]*scope_id:\s*workspaceScope\?\.scopeId,/,
  'SourcePanel should send the current course and workspace scope when launching deep search from the Q&A workspace',
);

assert.match(
  file,
  /setSelectedDocs\(nextSelectedDocs\)/,
  'SourcePanel should clear stale selected documents when a scoped document list changes',
);

assert.match(
  file,
  /setScopedSourceDocIds\(combinedFiles\.map\(\(file\) => file\.key\)\)/,
  'SourcePanel should publish the current visible scoped document ids for default RAG retrieval',
);

assert.match(
  file,
  /const loadRequestSequenceRef = useRef\(0\);/,
  'SourcePanel should track the latest scoped document load request to avoid stale responses overriding the current workspace',
);

assert.match(
  file,
  /if \(cancelled \|\| requestId !== loadRequestSequenceRef\.current\) \{\s*return;\s*\}/,
  'SourcePanel should ignore stale scoped document responses after the workspace changes',
);

console.log('sourcePanel.workspace-scope tests passed');

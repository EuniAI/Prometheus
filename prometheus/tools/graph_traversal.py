from pathlib import Path

from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from prometheus.parser import tree_sitter_parser
from prometheus.utils import neo4j_util

MAX_RESULT = 30

###############################################################################
#                          FileNode retrieval                                 #
###############################################################################


class FindFileNodeWithBasenameInput(BaseModel):
  basename: str = Field("The basename of FileNode to search for")


FIND_FILE_NODE_WITH_BASENAME_DESCRIPTION = """\
Find all FileNode in the graph with this basename of a file/dir. The basename must
include the extension, like 'bar.py', 'baz.java' or 'foo'
(in this case foo is a directory or a file without extension).

You can use this tool to check if a file/dir with this basename exists or get all
attributes related to the file/dir."""


def find_file_node_with_basename(
  basename: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""
      MATCH (f:FileNode {{ basename: '{basename}' }})
      RETURN f AS FileNode
      ORDER BY f.node_id
      LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class FindFileNodeWithRelativePathInput(BaseModel):
  relative_path: str = Field("The relative_path of FileNode to search for")


FIND_FILE_NODE_WITH_RELATIVE_PATH_DESCRIPTION = """\
Search FileNode in the graph with this relative_path of a file/dir. The relative_path is
the relative path from the root path of codebase. The relative_path must include the extension,
like 'foo/bar/baz.java'.

You can use this tool to check if a file/dir with this relative_path exists or get all
attributes related to the file/dir."""


def find_file_node_with_relative_path(
  relative_path: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode {{ relative_path: '{relative_path}' }})
    RETURN f AS FileNode
    ORDER BY f.node_id
    LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


###############################################################################
#                          ASTNode retrieval                                  #
###############################################################################


class FindASTNodeWithTextInFileWithBasenameInput(BaseModel):
  text: str = Field("Search ASTNode that exactly contains this text.")
  basename: str = Field("The basename of file/directory to search under for ASTNodes.")


FIND_AST_NODE_WITH_TEXT_IN_FILE_WITH_BASENAME_DESCRIPTION = """\
Find all ASTNode in the graph that exactly contains this text in any source file under 
a file/directory with this basename. For reliable results, search for longer, distinct text 
sequences rather than short common words or fragments. The contains is same as python's check 
`'foo' in text`, ie. it is case sensitive and is looking for exact matches. For best results, 
use unique text segments of at least several words. The basename can be either a file (like 
'bar.py', 'baz.java') or a directory (like 'src' or 'test')."""


def find_ast_node_with_text_in_file_with_basename(
  text: str, basename: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode) -[:HAS_FILE*0..]-> (c:FileNode) -[:HAS_AST]-> (:ASTNode) -[:PARENT_OF*0..]-> (a:ASTNode)
    WHERE f.basename = '{basename}' AND a.text CONTAINS '{text}'
    RETURN c as FileNode, a AS ASTNode
    ORDER BY SIZE(a.text)
    LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class FindASTNodeWithTextInFileWithRelativePathInput(BaseModel):
  text: str = Field("Search ASTNode that exactly contains this text.")
  relative_path: str = Field("The relative path of file/directory to search under for ASTNodes.")


FIND_AST_NODE_WITH_TEXT_IN_FILE_WITH_RELATIVE_PATH_DESCRIPTION = """\
Find all ASTNode in the graph that exactly contains this text in any source file under 
a file/directory with this relative path. For reliable results, search for longer, distinct text 
sequences rather than short common words or fragments. The contains is same as python's check `'foo' in text`, 
ie. it is case sensitive and is looking for exact matches. Therefore the search text should 
be exact as well. The relative path should be the path from the root of codebase 
(like 'src/core/parser.py' or 'test/unit')."""


def find_ast_node_with_text_in_file_with_relative_path(
  text: str, relative_path: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
        MATCH (f:FileNode) -[:HAS_FILE*0..]-> (c:FileNode) -[:HAS_AST]-> (:ASTNode) -[:PARENT_OF*0..]-> (a:ASTNode)
        WHERE f.relative_path = '{relative_path}' AND a.text CONTAINS '{text}'
        RETURN c as FileNode, a AS ASTNode
        ORDER BY SIZE(a.text)
        LIMIT {MAX_RESULT}
    """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class FindASTNodeWithTypeInFileWithBasenameInput(BaseModel):
  type: str = Field("Search ASTNode with this tree-sitter node type.")
  basename: str = Field("The basename of file/directory to search under for ASTNodes.")


FIND_AST_NODE_WITH_TYPE_IN_FILE_WITH_BASENAME_DESCRIPTION = """\
Find all ASTNode in the graph that has this tree-sitter node type in any source file under
a file/directory with this basename. This tool is useful for searching class/function/method
under a file/directory. The basename can be either a file (like 'bar.py', 
'baz.java') or a directory (like 'core' or 'test')."""


def find_ast_node_with_type_in_file_with_basename(
  type: str, basename: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode) -[:HAS_FILE*0..]-> (c:FileNode) -[:HAS_AST]-> (:ASTNode) -[:PARENT_OF*0..]-> (a:ASTNode)
    WHERE f.basename = '{basename}' AND a.type = '{type}'
    RETURN c as FileNode, a AS ASTNode
    ORDER BY SIZE(a.text)
    LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class FindASTNodeWithTypeInFileWithRelativePathInput(BaseModel):
  type: str = Field("Search ASTNode with this tree-sitter node type.")
  relative_path: str = Field("The relative path of file/directory to search under for ASTNodes.")


FIND_AST_NODE_WITH_TYPE_IN_FILE_WITH_RELATIVE_PATH_DESCRIPTION = """\
Find all ASTNode in the graph that has this tree-sitter node type in any source file under
a file/directory with this relative path. This tool is useful for searching class/function/method
under a file/directory. The relative path should be the path from the root 
of codebase (like 'src/core/parser.py' or 'test/unit')."""


def find_ast_node_with_type_in_file_with_relative_path(
  type: str, relative_path: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
        MATCH (f:FileNode) -[:HAS_FILE*0..]-> (c:FileNode) -[:HAS_AST]-> (:ASTNode) -[:PARENT_OF*0..]-> (a:ASTNode)
        WHERE f.relative_path = '{relative_path}' AND a.type = '{type}'
        RETURN c as FileNode, a AS ASTNode
        ORDER BY SIZE(a.text)
        LIMIT {MAX_RESULT}
    """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


###############################################################################
#                          TextNode retrieval                                 #
###############################################################################


class FindTextNodeWithTextInput(BaseModel):
  text: str = Field("Search TextNode that exactly contains this text.")


FIND_TEXT_NODE_WITH_TEXT_DESCRIPTION = """\
Find all TextNode in the graph that exactly contains this text. The contains is
same as python's check `'foo' in text`, ie. it is case sensitive and is
looking for exact matches. Therefore the search text should be exact as well.

You can use this tool to find all text/documentation in codebase that contains this text."""


def find_text_node_with_text(
  text: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode) -[:HAS_TEXT]-> (t:TextNode)
    WHERE t.text CONTAINS '{text}'
    RETURN f as FileNode, t AS TextNode
    ORDER BY t.node_id
    LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class FindTextNodeWithTextInFileInput(BaseModel):
  text: str = Field("Search TextNode that exactly contains this text.")
  basename: str = Field("The basename of FileNode to search TextNode.")


FIND_TEXT_NODE_WITH_TEXT_IN_FILE_DESCRIPTION = """\
Find all TextNode in the graph that exactly contains this text in a file with this basename.
The contains is same as python's check `'foo' in text`, ie. it is case sensitive and is
looking for exact matches. Therefore the search text should be exact as well.
The basename must include the extension, like 'bar.py', 'baz.java' or 'foo'
(in this case foo is a directory or a file without extension).

You can use this tool to find text/documentation in a specific file that contains this text."""


def find_text_node_with_text_in_file(
  text: str, basename: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode) -[:HAS_TEXT]-> (t:TextNode)
    WHERE f.basename = '{basename}' AND t.text CONTAINS '{text}'
    RETURN f as FileNode, t AS TextNode
    ORDER BY t.node_id
    LIMIT {MAX_RESULT}
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


class GetNextTextNodeWithNodeIdInput(BaseModel):
  node_id: int = Field("Get the next TextNode of this given node_id.")


GET_NEXT_TEXT_NODE_WITH_NODE_ID_DESCRIPTION = """\
Get the next TextNode of this given node_id.

You can use this tool to read the next section of text that you are interested in."""


def get_next_text_node_with_node_id(
  node_id: int, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  query = f"""\
    MATCH (f:FileNode) -[:HAS_TEXT]-> (a:TextNode {{ node_id: {node_id} }}) -[:NEXT_CHUNK]-> (b:TextNode)
    RETURN f as FileNode, b AS TextNode
  """
  return neo4j_util.run_neo4j_query(query, driver, max_token_per_result)


###############################################################################
#                                 Other                                       #
###############################################################################


class PreviewFileContentWithBasenameInput(BaseModel):
  basename: str = Field("The basename of FileNode to preview.")


PREVIEW_FILE_CONTENT_WITH_BASENAME_DESCRIPTION = """\
Preview the content of a file with this basename. The basename must include
the extension, like 'bar.py', 'baz.java' or 'foo' (in this case foo is a
directory or a file without extension).

You can use this tool to preview the content of a specific file to see what it contains
in the first 1000 lines or the first section. If the file is interesting, use other tools
to look at the file."""


def preview_file_content_with_basename(
  basename: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  source_code_query = f"""\
    MATCH (f:FileNode {{ basename: '{basename}' }}) -[:HAS_AST]-> (a:ASTNode)
    WITH f, apoc.text.split(a.text, '\\R') AS lines
    RETURN
      f AS FileNode,
      {{
        text: apoc.text.join(lines[0..1000], '\\n'),
        start_line: 1,
        end_line: 1000
      }} AS preview
    ORDER BY f.node_id
  """

  text_query = f"""\
    MATCH (f:FileNode {{ basename: '{basename}' }}) -[:HAS_TEXT]-> (t:TextNode)
    WHERE NOT EXISTS((:TextNode) -[:NEXT_CHUNK]-> (t))
    RETURN f as FileNode, t.text AS preview
    ORDER BY f.node_id
  """

  if tree_sitter_parser.supports_file(Path(basename)):
    return neo4j_util.run_neo4j_query(source_code_query, driver, max_token_per_result)
  return neo4j_util.run_neo4j_query(text_query, driver, max_token_per_result)


class PreviewFileContentWithRelativePathInput(BaseModel):
  relative_path: str = Field("The relative path of FileNode to preview.")


PREVIEW_FILE_CONTENT_WITH_RELATIVE_PATH_DESCRIPTION = """\
Preview the content of a file with this relative path from the root of codebase. 
The relative path must include the extension and full path from root, like 'src/core/parser.py', 
'test/unit/test_parser.java' or 'docs/README.md'.

You can use this tool to preview the content of a specific file to see what it contains
in the first 1000 lines or the first section. If the file is interesting, use other tools
to look at the file."""


def preview_file_content_with_relative_path(
  relative_path: str, driver: GraphDatabase.driver, max_token_per_result: int
) -> str:
  source_code_query = f"""\
      MATCH (f:FileNode {{ relative_path: '{relative_path}' }}) -[:HAS_AST]-> (a:ASTNode)
      WITH f, apoc.text.split(a.text, '\\R') AS lines
      RETURN 
        f as FileNode,
        {{
          text: apoc.text.join(lines[0..1000], '\\n'),
          start_line: 1,
          end_line: 1000
        }} AS preview
      ORDER BY f.node_id
  """

  text_query = f"""\
      MATCH (f:FileNode {{ relative_path: '{relative_path}' }}) -[:HAS_TEXT]-> (t:TextNode)
      WHERE NOT EXISTS((:TextNode) -[:NEXT_CHUNK]-> (t))
      RETURN f as FileNode, t.text AS preview
      ORDER BY f.node_id
  """

  if tree_sitter_parser.supports_file(Path(relative_path)):
    return neo4j_util.run_neo4j_query(source_code_query, driver, max_token_per_result)
  return neo4j_util.run_neo4j_query(text_query, driver, max_token_per_result)


class ReadCodeWithBasenameInput(BaseModel):
  basename: str = Field("The basename of FileNode to read.")
  start_line: int = Field("The starting line number, 1-indexed and inclusive.")
  end_line: int = Field("The ending line number, 1-indexed and exclusive.")


READ_CODE_WITH_BASENAME_DESCRIPTION = """\
Read a specific section of a source code file's content by specifying its basename and line range. 
The basename must include the extension, like 'bar.py' or 'baz.java'

This tool ONLY works with source code files (not text files or documentation). It is designed 
to read large sections of code at once - you should request substantial chunks (hundreds of lines) 
rather than making multiple small requests of 10-20 lines each, which would be inefficient.

Line numbers are 1-indexed, where start_line is inclusive and end_line is exclusive. 

This tool is useful for examining specific sections of source code files when you know 
the exact line range you want to analyze. The function will return an error message if 
end_line is less than start_line.
"""


def read_code_with_basename(
  basename: str,
  start_line: int,
  end_line: int,
  driver: GraphDatabase.driver,
  max_token_per_result: int,
) -> str:
  if end_line < start_line:
    return f"end_line {end_line} must be greater than start_line {start_line}"

  source_code_query = f"""\
    MATCH (f:FileNode {{ basename: '{basename}' }}) -[:HAS_AST]-> (a:ASTNode)
    WITH f, apoc.text.split(a.text, '\\R') AS lines
    RETURN
      f as FileNode,
      {{
        text: apoc.text.join(lines[{start_line - 1}..{end_line - 1}], '\\n'),
        start_line: {start_line},
        end_line: {end_line}
      }} AS SelectedLines
    ORDER BY f.node_id
  """

  return neo4j_util.run_neo4j_query(source_code_query, driver, max_token_per_result)


class ReadCodeWithRelativePathInput(BaseModel):
  relative_path: str = Field("The relative path of FileNode to read from root of codebase.")
  start_line: int = Field("The starting line number, 1-indexed and inclusive.")
  end_line: int = Field("The ending line number, 1-indexed and exclusive.")


READ_CODE_WITH_RELATIVE_PATH_DESCRIPTION = """\
Read a specific section of a source code file's content by specifying its relative path and line range. 
The relative path must be the full path from the root of codebase, like 'src/core/parser.py' or 
'test/unit/test_parser.java'.

This tool ONLY works with source code files (not text files or documentation). It is designed 
to read large sections of code at once - you should request substantial chunks (hundreds of lines) 
rather than making multiple small requests of 10-20 lines each, which would be inefficient.

Line numbers are 1-indexed, where start_line is inclusive and end_line is exclusive. 

This tool is useful for examining specific sections of source code files when you know 
the exact line range you want to analyze. The function will return an error message if 
end_line is less than start_line.
"""


def read_code_with_relative_path(
  relative_path: str,
  start_line: int,
  end_line: int,
  driver: GraphDatabase.driver,
  max_token_per_result: int,
) -> str:
  if end_line < start_line:
    return f"end_line {end_line} must be greater than start_line {start_line}"

  source_code_query = f"""\
        MATCH (f:FileNode {{ relative_path: '{relative_path}' }}) -[:HAS_AST]-> (a:ASTNode)
        WITH f, apoc.text.split(a.text, '\\R') AS lines
        RETURN
          f as FileNode,
          {{
            text: apoc.text.join(lines[{start_line - 1}..{end_line - 1}], '\\n'),
            start_line: {start_line},
            end_line: {end_line}
          }} AS SelectedLines
        ORDER BY f.node_id
    """

  return neo4j_util.run_neo4j_query(source_code_query, driver, max_token_per_result)

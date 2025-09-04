from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
from dataclasses import dataclass

from pydantic import BaseModel, Field

from prometheus.graph.graph_types import KnowledgeGraphNode
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.parser import tree_sitter_parser
from prometheus.utils.knowledge_graph_utils import format_knowledge_graph_data
from prometheus.utils.str_util import pre_append_line_numbers

MAX_RESULT = 5

"""
Tools for retrieving nodes from the KnowledgeGraph.
These tools allow you to search for FileNode, ASTNode, and TextNode based on various attributes
like basename, relative path, text content, and node type.

Returns a list of dictionaries containing the found nodes and their attributes.
"""

@dataclass
class ToolSpec:
    description: str
    input_schema: type


class FindFileNodeWithBasenameInput(BaseModel):
    basename: str = Field("The basename of FileNode to search for")

class FindFileNodeWithRelativePathInput(BaseModel):
    relative_path: str = Field("The relative_path of FileNode to search for")

class FindASTNodeWithTextInFileWithBasenameInput(BaseModel):
    text: str = Field("Search ASTNode that exactly contains this text.")
    basename: str = Field("The basename of file/directory to search under for ASTNodes.")

class FindASTNodeWithTextInFileWithRelativePathInput(BaseModel):
    text: str = Field("Search ASTNode that exactly contains this text.")
    relative_path: str = Field("The relative path of file/directory to search under for ASTNodes.")

class FindASTNodeWithTypeInFileWithBasenameInput(BaseModel):
    type: str = Field("Search ASTNode with this tree-sitter node type.")
    basename: str = Field("The basename of file/directory to search under for ASTNodes.")

class FindASTNodeWithTypeInFileWithRelativePathInput(BaseModel):
    type: str = Field("Search ASTNode with this tree-sitter node type.")
    relative_path: str = Field("The relative path of file/directory to search under for ASTNodes.")

class FindTextNodeWithTextInput(BaseModel):
    text: str = Field("Search TextNode that exactly contains this text.")

class FindTextNodeWithTextInFileInput(BaseModel):
    text: str = Field("Search TextNode that exactly contains this text.")
    basename: str = Field("The basename of FileNode to search TextNode.")

class GetNextTextNodeWithNodeIdInput(BaseModel):
    node_id: int = Field("Get the next TextNode of this given node_id.")

class PreviewFileContentWithBasenameInput(BaseModel):
    basename: str = Field("The basename of FileNode to preview.")

class PreviewFileContentWithRelativePathInput(BaseModel):
    relative_path: str = Field("The relative path of FileNode to preview.")

class ReadCodeWithBasenameInput(BaseModel):
    basename: str = Field("The basename of FileNode to read.")
    start_line: int = Field("The starting line number, 1-indexed and inclusive.")
    end_line: int = Field("The ending line number, 1-indexed and exclusive.")

class ReadCodeWithRelativePathInput(BaseModel):
    relative_path: str = Field("The relative path of FileNode to read from root of codebase.")
    start_line: int = Field("The starting line number, 1-indexed and inclusive.")
    end_line: int = Field("The ending line number, 1-indexed and exclusive.")



class GraphTraversalTool:

    # FileNode retrieval tools
    find_file_node_with_basename_spec = ToolSpec(
        description="""Find all FileNode in the graph with this basename of a file/dir. The basename must
        include the extension, like 'bar.py', 'baz.java' or 'foo'
        (in this case foo is a directory or a file without extension).

        You can use this tool to check if a file/dir with this basename exists or get all
        attributes related to the file/dir.""",
        input_schema=FindFileNodeWithBasenameInput
    )

    find_file_node_with_relative_path_spec = ToolSpec(
        description="""Search FileNode in the graph with this relative_path of a file/dir. The relative_path is
        the relative path from the root path of codebase. The relative_path must include the extension,
        like 'foo/bar/baz.java'.

        You can use this tool to check if a file/dir with this relative_path exists or get all
        attributes related to the file/dir.""",
        input_schema=FindFileNodeWithRelativePathInput
    )

    # ASTNode retrieval tools
    find_ast_node_with_text_in_file_with_basename_spec = ToolSpec(
        description="""Find all ASTNode in the graph that exactly contains this text in any source file with this basename.
        For reliable results, search for longer, distinct text sequences rather than short common words or fragments.
        The contains is same as python's check `'foo' in text`, ie. it is case sensitive and is looking for exact matches.
        For best results, use unique text segments of at least several words. The basename can be either a file (like 
        'bar.py', 'baz.java').""",
        input_schema=FindASTNodeWithTextInFileWithBasenameInput
    )

    find_ast_node_with_text_in_file_with_relative_path_spec = ToolSpec(
        description="""Find all ASTNode in the graph that exactly contains this text in any source file with this relative path.
        For reliable results, search for longer, distinct text sequences rather than short common words or fragments.
        The contains is same as python's check `'foo' in text`, ie. it is case sensitive and is looking for exact matches.
        Therefore the search text should be exact as well. The relative path should be the path from the root of codebase 
        (like 'src/core/parser.py').""",
        input_schema=FindASTNodeWithTextInFileWithRelativePathInput
    )

    find_ast_node_with_type_in_file_with_basename_spec = ToolSpec(
        description="""Find all ASTNode in the graph that has this tree-sitter node type in any source file with this basename.
        This tool is useful for searching class/function/method under files.""",
        input_schema=FindASTNodeWithTypeInFileWithBasenameInput
    )

    find_ast_node_with_type_in_file_with_relative_path_spec = ToolSpec(
        description="""Find all ASTNode in the graph that has this tree-sitter node type in any source file with this relative path.
        This tool is useful for searching class/function/method under a file.""",
        input_schema=FindASTNodeWithTypeInFileWithRelativePathInput
    )

    # TextNode retrieval tools
    find_text_node_with_text_spec = ToolSpec(
        description="""Find all TextNode in the graph that exactly contains this text. The contains is
        same as python's check `'foo' in text`, ie. it is case sensitive and is
        looking for exact matches. Therefore the search text should be exact as well.

        You can use this tool to find all text/documentation in codebase that contains this text.""",
        input_schema=FindTextNodeWithTextInput
    )

    find_text_node_with_text_in_file_spec = ToolSpec(
        description="""Find all TextNode in the graph that exactly contains this text in a file with this basename.
        The contains is same as python's check `'foo' in text`, ie. it is case sensitive and is
        looking for exact matches. Therefore the search text should be exact as well.
        The basename must include the extension, like 'bar.py', 'baz.java' or 'foo'
        (in this case foo is a file without extension).

        You can use this tool to find text/documentation in a specific file that contains this text.""",
        input_schema=FindTextNodeWithTextInFileInput
    )

    get_next_text_node_with_node_id_spec = ToolSpec(
        description="""Get the next TextNode of this given node_id.

        You can use this tool to read the next section of text that you are interested in.""",
        input_schema=GetNextTextNodeWithNodeIdInput
    )

    read_code_with_relative_path_spec = ToolSpec(
        description="""Read a specific section of a source code file's content by specifying its relative path and line range. 
        The relative path must be the full path from the root of codebase, like 'src/core/parser.py' or 
        'test/unit/test_parser.java'.

        This tool ONLY works with source code files (not text files or documentation). It is designed 
        to read large sections of code at once - you should request substantial chunks (hundreds of lines) 
        rather than making multiple small requests of 10-20 lines each, which would be inefficient.

        Line numbers are 1-indexed, where start_line is inclusive and end_line is exclusive. 

        This tool is useful for examining specific sections of source code files when you know 
        the exact line range you want to analyze. The function will return an error message if 
        end_line is less than start_line.""",
        input_schema=ReadCodeWithRelativePathInput
    )

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg


    ###############################################################################
    #                          FileNode retrieval                                 #
    ###############################################################################

    def find_file_node_with_basename(self, basename: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all FileNodes with the given basename."""
        results = []
        for kg_node in self.kg.get_file_nodes():
            if kg_node.node.basename == basename:
                results.append(
                    {
                        "FileNode": {
                            "node_id": kg_node.node_id,
                            "basename": kg_node.node.basename,
                            "relative_path": kg_node.node.relative_path,
                        }
                    }
                )
        results.sort(key=lambda x: x["FileNode"]["node_id"])
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]

    def find_file_node_with_relative_path(self, relative_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all FileNodes with the given relative path."""
        results = []
        for kg_node in self.kg.get_file_nodes():
            if kg_node.node.relative_path == relative_path:
                results.append(
                    {
                        "FileNode": {
                            "node_id": kg_node.node_id,
                            "basename": kg_node.node.basename,
                            "relative_path": kg_node.node.relative_path,
                        }
                    }
                )
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]


    ###############################################################################
    #                          ASTNode retrieval                                  #
    ###############################################################################

    def find_ast_node_with_text_in_file(
        self, text: str, target_files_nodes: List[KnowledgeGraphNode]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes containing the given text in files with the given basename."""
        results = []

        # Get HAS_AST edges to find which AST nodes belong to these files
        has_ast_edges = self.kg.get_has_ast_edges()
        file_to_ast_map = {
            edge.source.node_id: edge.target
            for edge in has_ast_edges
            if edge.source.node_id in [n.node_id for n in target_files_nodes]
        }

        # Construct parent to children map for AST traversal
        parent_to_children = self.kg.get_parent_to_children_map()

        # Get root AstNode id list
        root_ast_node_ids = set([node.node_id for node in file_to_ast_map.values()])

        for file_node in target_files_nodes:
            # Start with root AST node for this file
            root_ast = file_to_ast_map[file_node.node_id]

            # Add all descendant AST nodes
            stack = [root_ast]
            while stack:
                current_node = stack.pop()

                # Check if the current node contains the text
                # Don't include the root AST node itself
                if text in current_node.node.text and current_node.node_id not in root_ast_node_ids:
                    results.append(
                        {
                            "FileNode": {
                                "node_id": file_node.node_id,
                                "basename": file_node.node.basename,
                                "relative_path": file_node.node.relative_path,
                            },
                            "ASTNode": {
                                "node_id": current_node.node_id,
                                "type": current_node.node.type,
                                "start_line": current_node.node.start_line,
                                "end_line": current_node.node.end_line,
                                "text": current_node.node.text,
                            },
                        }
                    )

                # Add children to stack
                stack += parent_to_children.get(current_node.node_id, [])

        # Sort by text length (smaller first)
        results.sort(key=lambda x: len(x["ASTNode"]["text"]))
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]

    def find_ast_node_with_text_in_file_with_basename(self, text: str, basename: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes containing the given text in files with the given basename."""
        # Get file nodes with the given basename
        target_files_nodes: List[KnowledgeGraphNode] = [
            node for node in self.kg.get_file_nodes() if node.node.basename == basename
        ]
        return self.find_ast_node_with_text_in_file(text, target_files_nodes)


    def find_ast_node_with_text_in_file_with_relative_path(self, text: str, relative_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes containing the given text in files with the given relative path."""
        # Get file nodes with the given basename
        target_files_nodes: List[KnowledgeGraphNode] = [
            node for node in self.kg.get_file_nodes() if node.node.relative_path == relative_path
        ]
        return self.find_ast_node_with_text_in_file(text, target_files_nodes)

    def find_ast_node_with_type_in_file(
        self, type: str, target_files_nodes: List[KnowledgeGraphNode]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes containing the given text in files with the given basename."""
        results = []

        # Get HAS_AST edges to find which AST nodes belong to these files
        has_ast_edges = self.kg.get_has_ast_edges()
        file_to_ast_map = {
            edge.source.node_id: edge.target
            for edge in has_ast_edges
            if edge.source.node_id in [n.node_id for n in target_files_nodes]
        }

        # Construct parent to children map for AST traversal
        parent_to_children = self.kg.get_parent_to_children_map()

        # Get root AstNode id list
        root_ast_node_ids = set([node.node_id for node in file_to_ast_map.values()])

        for file_node in target_files_nodes:
            # Start with root AST node for this file
            root_ast = file_to_ast_map[file_node.node_id]

            # Add all descendant AST nodes
            stack = [root_ast]
            while stack:
                current_node = stack.pop()

                # Check if current node contains the text
                # Don't include the root AST node itself
                if current_node.node.type == type and current_node.node_id not in root_ast_node_ids:
                    results.append(
                        {
                            "FileNode": {
                                "node_id": file_node.node_id,
                                "basename": file_node.node.basename,
                                "relative_path": file_node.node.relative_path,
                            },
                            "ASTNode": {
                                "node_id": current_node.node_id,
                                "type": current_node.node.type,
                                "start_line": current_node.node.start_line,
                                "end_line": current_node.node.end_line,
                                "text": current_node.node.text,
                            },
                        }
                    )

                # Add children to stack
                stack += parent_to_children.get(current_node.node_id, [])

        # Sort by text length (smaller first)
        results.sort(key=lambda x: len(x["ASTNode"]["text"]))
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]

    def find_ast_node_with_type_in_file_with_basename(self, type: str, basename: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes with the given type in files with the given basename."""
        # Get file nodes with the given basename
        target_files_nodes: List[KnowledgeGraphNode] = [
            node for node in self.kg.get_file_nodes() if node.node.basename == basename
        ]
        return self.find_ast_node_with_type_in_file(type, target_files_nodes)


    def find_ast_node_with_type_in_file_with_relative_path(self, type: str, relative_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all ASTNodes with the given type in files with the given relative path."""
        # Get file nodes with the given basename
        target_files_nodes: List[KnowledgeGraphNode] = [
            node for node in self.kg.get_file_nodes() if node.node.relative_path == relative_path
        ]
        return self.find_ast_node_with_type_in_file(type, target_files_nodes)


    ###############################################################################
    #                          TextNode retrieval                                 #
    ###############################################################################

    def find_file_node_of_a_text_node(self, text_node: KnowledgeGraphNode) -> KnowledgeGraphNode:
        """
        Find a file node that contains the given text node.
        """
        next_chunk_reverse_map = {
            edge.target.node_id: edge.source for edge in self.kg.get_next_chunk_edges()
        }
        has_file_node_map = {edge.target.node_id: edge.source for edge in self.kg.get_has_text_edges()}

        # Find the root text node
        current_text_node = text_node
        while next_chunk_reverse_map.get(current_text_node.node_id, None) is not None:
            current_text_node = next_chunk_reverse_map[current_text_node.node_id]

        # Now current_text_node is the root text node
        file_node = has_file_node_map[current_text_node.node_id]
        return file_node

    def find_text_node_with_text(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all TextNodes containing the given text."""
        results = []
        # Find text nodes that contain the given text
        text_nodes_with_text = [node for node in self.kg.get_text_nodes() if text in node.node.text]

        # If no text nodes found, return early
        if not text_nodes_with_text:
            return format_knowledge_graph_data([]), []
        for text_node in text_nodes_with_text:
            # Find the file node that contains this text node
            file_node = self.find_file_node_of_a_text_node(text_node)
            results.append(
                {
                    "FileNode": {
                        "node_id": file_node.node_id,
                        "basename": file_node.node.basename,
                        "relative_path": file_node.node.relative_path,
                    },
                    "TextNode": {
                        "node_id": text_node.node_id,
                        "text": text_node.node.text,
                        "start_line": text_node.node.start_line,
                        "end_line": text_node.node.end_line,
                    },
                }
            )

        # Sort by node_id
        results.sort(key=lambda x: x["TextNode"]["node_id"])
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]


    def find_text_node_with_text_in_file(
        self, text: str, basename: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Find all TextNodes containing the given text in files with the given basename."""
        results = []
        # Find text nodes that contain the given text
        text_nodes_with_text = [node for node in self.kg.get_text_nodes() if text in node.node.text]

        # If no text nodes found, return early
        if not text_nodes_with_text:
            return format_knowledge_graph_data([]), []

        for text_node in text_nodes_with_text:
            # Now current_text_node is the root text node
            file_node = self.find_file_node_of_a_text_node(text_node)

            # If the file node matches the given basename, add to results
            if file_node.node.basename == basename:
                results.append(
                    {
                        "FileNode": {
                            "node_id": file_node.node_id,
                            "basename": file_node.node.basename,
                            "relative_path": file_node.node.relative_path,
                        },
                        "TextNode": {
                            "node_id": text_node.node_id,
                            "text": text_node.node.text,
                            "start_line": text_node.node.start_line,
                            "end_line": text_node.node.end_line,
                        },
                    }
                )

        # Sort by node_id
        results.sort(key=lambda x: x["TextNode"]["node_id"])
        return format_knowledge_graph_data(results[:MAX_RESULT]), results[:MAX_RESULT]


    def get_next_text_node_with_node_id(self, node_id: int) -> Tuple[str, List[Dict[str, Any]]]:
        """Get the next TextNode for the given node_id."""

        results = []

        # Find the current text node
        current_text_node = None
        for node in self.kg.get_text_nodes():
            if node.node_id == node_id:
                current_text_node = node
                break

        # If the current text node does not exist, return empty result
        if not current_text_node:
            return format_knowledge_graph_data([]), []

        # Get next chunk map
        next_chunk_map = {edge.source.node_id: edge.target for edge in self.kg.get_next_chunk_edges()}

        # Get the next text node
        next_text_node = next_chunk_map.get(current_text_node.node_id, None)

        # if the next text node does not exist, return empty result
        if not next_text_node:
            return format_knowledge_graph_data([]), []

        # Find the file node that contains this text node
        file_node = self.find_file_node_of_a_text_node(next_text_node)
        results.append(
            {
                "FileNode": {
                    "node_id": file_node.node_id,
                    "basename": file_node.node.basename,
                    "relative_path": file_node.node.relative_path,
                },
                "TextNode": {
                    "node_id": next_text_node.node_id,
                    "text": next_text_node.node.text,
                    "start_line": next_text_node.node.start_line,
                    "end_line": next_text_node.node.end_line,
                },
            }
        )
        return format_knowledge_graph_data(results), results


    ###############################################################################
    #                                 Other                                       #
    ###############################################################################


    def read_code_with_relative_path(self, relative_path: str, start_line: int, end_line: int) -> Union[Tuple[str, List[Dict[str, Any]]], Tuple[str, None]]:
        """Read a specific section of a source code file by relative path and line range."""
        if end_line < start_line:
            return f"end_line {end_line} must be greater than start_line {start_line}!", None

        # Find file nodes with the given relative path
        target_file = None
        for node in self.kg.get_file_nodes():
            if node.node.relative_path == relative_path:
                target_file = node
                break

        # Check if the file exists
        if not target_file:
            return format_knowledge_graph_data([]), []

        # Check if it is a source code file
        if not tree_sitter_parser.supports_file(Path(target_file.node.relative_path)):
            return f"The file {relative_path} is not a source code file!", None

        # Get the first ast node for this file
        first_ast_node = [
            edge.target for edge in self.kg.get_has_ast_edges() if edge.source.node_id == target_file.node_id
        ][0]
        text = first_ast_node.node.text
        lines = text.split("\n")
        selected_lines = lines[start_line - 1 : end_line]  # Convert to 0-indexed
        selected_text = "\n".join(selected_lines)
        selected_text_with_line_numbers = pre_append_line_numbers(selected_text, start_line)

        result_data = [
            {
                "FileNode": {
                    "node_id": target_file.node_id,
                    "basename": target_file.node.basename,
                    "relative_path": target_file.node.relative_path,
                },
                "SelectedLines": {
                    "text": selected_text_with_line_numbers,
                    "start_line": start_line,
                    "end_line": end_line,
                },
            }
        ]
        return format_knowledge_graph_data(result_data), result_data

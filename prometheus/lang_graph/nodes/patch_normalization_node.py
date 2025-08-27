"""Patch Normalization and Selection Node

This module implements simplified patch normalization and direct selection functionality.
Provides standardized patch candidates with direct best patch selection.
"""

import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence

from prometheus.lang_graph.subgraphs.issue_not_verified_bug_state import IssueNotVerifiedBugState


@dataclass
class PatchMetrics:
    """Patch basic metrics"""

    occurrence_count: int = 1


@dataclass
class NormalizedPatch:
    """Normalized patch data structure"""

    original_index: int
    original_content: str
    normalized_content: str
    metrics: PatchMetrics


class PatchNormalizationNode:
    """Patch Normalization and Direct Selection Node

    Implements patch normalization, deduplication and direct best patch selection.
    Simplified approach without complex voting mechanisms.
    """

    def __init__(self):
        self._logger = logging.getLogger(
            f"thread-{threading.get_ident()}.prometheus.lang_graph.nodes.patch_normalization_node"
        )

    def normalize_patch(self, raw_patch: str) -> str:
        """Normalize patch content for deduplication

        Removes metadata lines and standardizes formatting to enable
        accurate patch comparison and deduplication.
        """
        if not raw_patch:
            return ""

        lines = raw_patch.split("\n")
        normalized_lines = []

        for line in lines:
            # Skip metadata lines
            if self._is_metadata_line(line):
                continue

            # Normalize file paths
            if line.startswith("--- ") or line.startswith("+++ "):
                line = self._normalize_file_path(line)

            normalized_lines.append(line)

        return "\n".join(normalized_lines)

    def _is_metadata_line(self, line: str) -> bool:
        """Check if line is metadata that should be ignored"""
        metadata_patterns = [
            r"^diff --git",
            r"^index [a-f0-9]+\.\.[a-f0-9]+",
            r"^new file mode \d+",
            r"^deleted file mode \d+",
            r"^similarity index \d+%",
            r"^rename from ",
            r"^rename to ",
            r"^Binary files ",
        ]

        return any(re.match(pattern, line) for pattern in metadata_patterns)

    def _normalize_file_path(self, line: str) -> str:
        """Normalize file path in diff header"""
        # Remove timestamp and mode information
        line = re.sub(r"\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)? \+\d{4}", "", line)
        line = re.sub(r"\s+\d{6}", "", line)

        return line

    def calculate_patch_metrics(self, normalized_patch: str) -> PatchMetrics:
        """Calculate basic metrics for a patch"""
        return PatchMetrics()

    def deduplicate_patches(self, patches: Sequence[str]) -> List[NormalizedPatch]:
        """Deduplicate patches using normalization

        Returns list of unique normalized patches with occurrence counts.
        """
        if not patches:
            return []

        # Normalize all patches
        normalized_patches = []
        for i, patch in enumerate(patches):
            normalized_content = self.normalize_patch(patch)
            metrics = self.calculate_patch_metrics(normalized_content)

            normalized_patches.append(
                NormalizedPatch(
                    original_index=i,
                    original_content=patch,
                    normalized_content=normalized_content,
                    metrics=metrics,
                )
            )

        # Group by normalized content
        patch_groups = defaultdict(list)
        for patch in normalized_patches:
            patch_groups[patch.normalized_content].append(patch)

        # Create deduplicated list with occurrence counts
        deduplicated = []
        for normalized_content, group in patch_groups.items():
            # Use the first patch in the group as representative
            representative = group[0]
            # Update occurrence count
            representative.metrics.occurrence_count = len(group)
            deduplicated.append(representative)

        self._logger.info(
            f"Deduplication complete: {len(patches)} -> {len(deduplicated)} unique patches"
        )

        return deduplicated

    def __call__(self, state: IssueNotVerifiedBugState) -> Dict:
        """Node call interface

        Process edit_patches in state, return normalized, deduplicated patches
        """
        patches = state.get("edit_patches", [])

        if not patches:
            self._logger.warning("No patches found to process")
            return {
                "deduplicated_patches": [],
            }

        self._logger.info(f"Starting to process {len(patches)} patches")

        # Execute deduplication and normalization
        normalized_patches = self.deduplicate_patches(patches)

        # Return deduplicated patches (selection will be done by final_patch_selection_node)
        deduplicated_patches = [patch.original_content for patch in normalized_patches]

        self._logger.info(
            f"Patch processing complete, deduplicated to {len(deduplicated_patches)} unique patches"
        )

        return {
            "deduplicated_patches": deduplicated_patches,
        }

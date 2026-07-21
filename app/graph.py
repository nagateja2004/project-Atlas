import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx

from app.models import Document

if TYPE_CHECKING:
    from app.ingestion import Chunk


class GraphStore:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.graphs: dict[uuid.UUID, nx.MultiDiGraph] = {}

    def update(self, document: Document, chunks: list["Chunk"]) -> None:
        graph = self._graph(document.project_id)
        project_id = str(document.project_id)
        project_node = f"project:{project_id}"
        document_node = f"document:{document.id}"
        graph.add_node(project_node, type="Project", label=project_id)
        graph.add_node(document_node, type="Document", label=document.filename, document_type=document.document_type)
        graph.add_edge(project_node, document_node, relation="contains")
        metadata = document.metadata_json or {}
        equipment = metadata.get("equipment_tags", [])
        for tag in equipment if isinstance(equipment, list) else []:
            node = f"equipment:{project_id}:{tag}"
            graph.add_node(node, type="Equipment", label=tag)
            graph.add_edge(document_node, node, relation="references")
        vendor = metadata.get("vendor")
        if isinstance(vendor, str):
            vendor_node = f"vendor:{project_id}:{vendor.lower()}"
            graph.add_node(vendor_node, type="Vendor", label=vendor)
            graph.add_edge(document_node, vendor_node, relation="submitted_by")
            for tag in equipment if isinstance(equipment, list) else []:
                graph.add_edge(f"equipment:{project_id}:{tag}", vendor_node, relation="supplied_by")
        references = metadata.get("spec_references", [])
        for reference in references if isinstance(references, list) else []:
            node = f"specification:{project_id}:{reference}"
            graph.add_node(node, type="SpecificationSection", label=reference)
            graph.add_edge(document_node, node, relation="references")
        if document.document_type == "RFI":
            node = f"rfi:{document.id}"
            graph.add_node(node, type="RFI", label=document.filename, status=metadata.get("rfi_status", "unknown"))
            graph.add_edge(project_node, node, relation="has_rfi")
            graph.add_edge(node, document_node, relation="source_document")
        if document.document_type == "schedule":
            for chunk in chunks:
                if chunk.section.startswith("Task "):
                    node = f"schedule_task:{document.project_id}:{chunk.section[5:]}"
                    graph.add_node(node, type="ScheduleTask", label=chunk.section[5:])
                    graph.add_edge(document_node, node, relation="contains")
        if document.document_type == "commissioning_record":
            node = f"test_procedure:{document.id}"
            graph.add_node(node, type="TestProcedure", label=document.filename)
            graph.add_edge(document_node, node, relation="contains")
        self._persist(document.project_id, graph)

    def export(self, project_id: uuid.UUID) -> dict[str, object]:
        graph = self._graph(project_id)
        return {
            "project_id": str(project_id),
            "nodes": [{"id": node, **data} for node, data in graph.nodes(data=True)],
            "edges": [
                {"source": source, "target": target, "key": key, **data}
                for source, target, key, data in graph.edges(keys=True, data=True)
            ],
        }

    def _graph(self, project_id: uuid.UUID) -> nx.MultiDiGraph:
        if project_id not in self.graphs:
            graph = nx.MultiDiGraph()
            path = self.directory / f"{project_id}.json"
            if path.exists():
                payload = json.loads(path.read_text())
                for node in payload.get("nodes", []):
                    graph.add_node(node["id"], **{key: value for key, value in node.items() if key != "id"})
                for edge in payload.get("edges", []):
                    graph.add_edge(
                        edge["source"],
                        edge["target"],
                        key=edge.get("key"),
                        **{key: value for key, value in edge.items() if key not in {"source", "target", "key"}},
                    )
            self.graphs[project_id] = graph
        return self.graphs[project_id]

    def _persist(self, project_id: uuid.UUID, graph: nx.MultiDiGraph) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{project_id}.json").write_text(json.dumps(self.export(project_id), indent=2))

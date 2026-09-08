from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import yaml

from .evidence import EvidenceIndex
from .models import (
    DecisionRecord,
    DocumentKind,
    FieldSpec,
    GenerateRequest,
    IntegrationContext,
    OperationMapping,
    RestConsumerSpec,
    SoapFaultSpec,
    SoapOperationSpec,
    SoapServiceSpec,
    SoapVersion,
    TraceStep,
)


class ContextAnalysisError(ValueError):
    pass


@dataclass
class AnalysisOutput:
    context: IntegrationContext
    evidence: EvidenceIndex
    trace: TraceStep


class ContextAnalyzer:
    """Normalizes structured input and performs conservative WSDL/OpenAPI extraction."""

    def analyze(self, request: GenerateRequest) -> AnalysisOutput:
        evidence = EvidenceIndex()
        document_evidence: dict[str, list[str]] = {}
        total_bytes = 0
        for document in request.documents:
            total_bytes += len(document.content.encode("utf-8"))
            document_evidence[document.name] = evidence.add_document_lines(document)

        if request.context is not None:
            context = request.context
            self._index_context(context, evidence)
            extraction_note = "Used the supplied structured integration contract as authoritative."
        else:
            context = self._context_from_documents(request, evidence)
            self._index_context(context, evidence, source="inferred.context")
            extraction_note = (
                "Inferred a conservative integration contract from supplied documents."
            )

        warnings: list[str] = []
        if not context.soap_service.endpoint:
            warnings.append(
                "No SOAP endpoint was supplied; generated live tests require SOAP_ENDPOINT."
            )
        if context.rest_consumer is None:
            warnings.append(
                "No REST consumer contract was supplied; REST mapping coverage is limited."
            )
        if not any(operation.fields for operation in context.soap_service.operations):
            warnings.append("No request fields were discovered; field-level scenarios are limited.")

        decisions = [
            DecisionRecord(
                decision="Treat explicit structured context as authoritative when it conflicts with documents."
                if request.context
                else "Use only contract details that can be extracted deterministically.",
                basis=[item.id for item in evidence.items[:10]],
                consequence="Every generated scenario remains traceable; ambiguous details become warnings.",
            ),
            DecisionRecord(
                decision="Model the SOAP service and REST consumer as separate test layers.",
                basis=evidence.find(location_contains="soap_service")
                + evidence.find(location_contains="rest_consumer"),
                consequence="Failures can be isolated to the XML service contract or adapter mapping.",
            ),
        ]
        trace = TraceStep(
            sequence=1,
            agent="context-analyzer",
            phase="context_normalization",
            status="completed_with_warnings" if warnings else "completed",
            summary=f"{extraction_note} Indexed {len(evidence.items)} evidence records from {total_bytes} bytes of documents.",
            evidence_ids=[item.id for item in evidence.items],
            decisions=decisions,
            warnings=warnings,
        )
        return AnalysisOutput(context=context, evidence=evidence, trace=trace)

    def _index_context(
        self, context: IntegrationContext, evidence: EvidenceIndex, source: str = "request.context"
    ) -> None:
        payload = context.model_dump(mode="json")
        self._walk_and_index(payload, evidence, source, "context")

    def _walk_and_index(
        self, value: Any, evidence: EvidenceIndex, source: str, location: str
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                self._walk_and_index(child, evidence, source, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._walk_and_index(child, evidence, source, f"{location}[{index}]")
        elif value is not None and value != "":
            evidence.add(source, location, value)

    def _context_from_documents(
        self, request: GenerateRequest, evidence: EvidenceIndex
    ) -> IntegrationContext:
        wsdl_documents = [doc for doc in request.documents if doc.kind == DocumentKind.WSDL]
        if not wsdl_documents:
            raise ContextAnalysisError(
                "document-only analysis requires a WSDL; otherwise provide structured context"
            )
        soap_service = self._parse_wsdl(wsdl_documents[0])
        rest_consumer = None
        mappings: list[OperationMapping] = []
        openapi_documents = [doc for doc in request.documents if doc.kind == DocumentKind.OPENAPI]
        if openapi_documents:
            rest_consumer = self._parse_openapi(openapi_documents[0])
        requirements = "\n".join(
            doc.content for doc in request.documents if doc.kind == DocumentKind.REQUIREMENTS
        )
        purpose = self._first_meaningful_line(requirements) or (
            f"Exercise {soap_service.service_name} through its declared SOAP contract."
        )
        if rest_consumer:
            purpose += " Validate the consuming REST boundary independently."
        return IntegrationContext(
            system_name=f"{soap_service.service_name} integration",
            purpose=purpose,
            soap_service=soap_service,
            rest_consumer=rest_consumer,
            mappings=mappings,
            assumptions=[
                "Document-only extraction does not infer business semantics that are absent from the contract."
            ],
        )

    def _parse_wsdl(self, document: Any) -> SoapServiceSpec:
        try:
            root = ET.fromstring(document.content)
        except ET.ParseError as exc:
            raise ContextAnalysisError(f"invalid WSDL XML in {document.name}: {exc}") from exc

        target_namespace = root.attrib.get("targetNamespace")
        service_node = next(self._iter_local(root, "service"), None)
        service_name = (
            service_node.attrib.get("name", "DiscoveredSoapService")
            if service_node is not None
            else "DiscoveredSoapService"
        )

        endpoint = None
        for address_name in ("address",):
            address = next(self._iter_local(root, address_name), None)
            if address is not None and address.attrib.get("location"):
                endpoint = address.attrib["location"]
                break

        version = SoapVersion.SOAP_12 if "soap12" in document.content else SoapVersion.SOAP_11
        actions: dict[str, str] = {}
        for binding_operation in self._iter_local(root, "operation"):
            name = binding_operation.attrib.get("name")
            action = next(
                (
                    child.attrib.get("soapAction")
                    for child in list(binding_operation)
                    if self._local_name(child.tag) == "operation" and child.attrib.get("soapAction")
                ),
                None,
            )
            if name and action:
                actions[name] = action

        elements = self._schema_elements(root)
        operations: list[SoapOperationSpec] = []
        seen: set[str] = set()
        for port_operation in self._iter_local(root, "operation"):
            name = port_operation.attrib.get("name")
            has_io = any(
                self._local_name(child.tag) in {"input", "output", "fault"}
                for child in port_operation
            )
            if not name or not has_io or name in seen:
                continue
            seen.add(name)
            faults = [
                SoapFaultSpec(name=child.attrib.get("name", "DeclaredFault"))
                for child in port_operation
                if self._local_name(child.tag) == "fault"
            ]
            request_element = name
            fields = elements.get(name, [])
            operations.append(
                SoapOperationSpec(
                    name=name,
                    soap_action=actions.get(name),
                    request_element=request_element,
                    response_element=f"{name}Response",
                    fields=fields,
                    faults=faults,
                )
            )

        if not operations:
            raise ContextAnalysisError(f"no WSDL operations found in {document.name}")
        return SoapServiceSpec(
            service_name=service_name,
            endpoint=endpoint,
            target_namespace=target_namespace,
            version=version,
            operations=operations,
        )

    def _schema_elements(self, root: ET.Element) -> dict[str, list[FieldSpec]]:
        result: dict[str, list[FieldSpec]] = {}
        for element in self._iter_local(root, "element"):
            name = element.attrib.get("name")
            if not name:
                continue
            fields: list[FieldSpec] = []
            for child in element.iter():
                if child is element or self._local_name(child.tag) != "element":
                    continue
                child_name = child.attrib.get("name")
                if not child_name:
                    continue
                data_type = child.attrib.get("type", "string").split(":")[-1]
                required = child.attrib.get("minOccurs", "1") != "0"
                nullable = child.attrib.get("nillable", "false").lower() == "true"
                fields.append(
                    FieldSpec(
                        name=child_name,
                        data_type=data_type,
                        required=required,
                        nullable=nullable,
                    )
                )
            if fields:
                result[name] = fields
        return result

    def _parse_openapi(self, document: Any) -> RestConsumerSpec:
        try:
            payload = json.loads(document.content)
        except json.JSONDecodeError:
            try:
                payload = yaml.safe_load(document.content)
            except yaml.YAMLError as exc:
                raise ContextAnalysisError(
                    f"invalid OpenAPI document {document.name}: {exc}"
                ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("paths"), dict):
            raise ContextAnalysisError(f"OpenAPI document {document.name} has no paths object")
        for path, path_item in payload["paths"].items():
            if not isinstance(path_item, dict):
                continue
            for method in ("post", "put", "patch", "get", "delete"):
                if method not in path_item:
                    continue
                operation = path_item[method] or {}
                responses = operation.get("responses", {}) if isinstance(operation, dict) else {}
                success_status = next(
                    (
                        int(code)
                        for code in responses
                        if str(code).isdigit() and 200 <= int(code) < 300
                    ),
                    200,
                )
                servers = payload.get("servers") or []
                base_url = (
                    servers[0].get("url") if servers and isinstance(servers[0], dict) else None
                )
                title = (payload.get("info") or {}).get("title", "DiscoveredRestConsumer")
                return RestConsumerSpec(
                    service_name=title,
                    base_url=base_url,
                    endpoint=path,
                    method=method.upper(),
                    success_status=success_status,
                )
        raise ContextAnalysisError(f"OpenAPI document {document.name} has no supported operations")

    @staticmethod
    def _iter_local(root: ET.Element, local_name: str):
        return (node for node in root.iter() if ContextAnalyzer._local_name(node.tag) == local_name)

    @staticmethod
    def _local_name(tag: str) -> str:
        return re.sub(r"^\{[^}]+\}", "", tag)

    @staticmethod
    def _first_meaningful_line(value: str) -> str | None:
        return next((line.strip("# -\t") for line in value.splitlines() if line.strip()), None)

"""Separate task instructions from research evidence for context budgeting."""

from langchain_core.messages import HumanMessage


class EvidencePrompt:
    def __init__(self, workflow):
        self.workflow = workflow
        self._sources = []

    def add(self, label, text, *, compressible=True):
        self._sources.append((label, str(text), compressible))
        return self.workflow.render('shared_evidence_reference', label=label)

    def messages(self, instructions):
        return [HumanMessage(content=instructions), *(
            HumanMessage(
                content=self.workflow.render('shared_evidence_wrapper', label=label, text=text),
                additional_kwargs={
                    "research_evidence": compressible,
                    "research_evidence_source": label,
                    "source_label": label,
                },
            )
            for label, text, compressible in self._sources
        )]

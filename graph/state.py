"""StructPilot v2.0 - LangGraph State Definition."""



from __future__ import annotations



from dataclasses import dataclass, field

from datetime import datetime

from typing import Any, Dict, List, Literal, Optional



CheckpointStatus = Literal["pending", "in_progress", "passed", "failed", "skipped"]

SoftwareTarget = Literal["cryosparc", "relion", "both"]
ResponseProfile = Literal["concise", "teaching", "expert"]

ActionTag = Literal[
    "stage_guide", "qc_check", "advance", "rollback", "progress", "report",
    "param_advice", "fault_diagnosis", "plot_interpretation", "general", "error",
    "concept_explain", "casual",
]




@dataclass

class CheckpointRecord:

    cp_id: str

    cp_name_cn: str

    status: CheckpointStatus = "pending"

    entered_at: Optional[str] = None

    completed_at: Optional[str] = None

    user_feedback: str = ""

    qc_summary: str = ""

    qc_passed: bool = False

    params_captured: Dict[str, Any] = field(default_factory=dict)

    notes: str = ""





@dataclass

class Message:

    role: Literal["user", "assistant", "system"]

    content: str

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    action_tag: ActionTag = "general"

    metadata: Dict[str, Any] = field(default_factory=dict)

    image_refs: List[Dict[str, Any]] = field(default_factory=list)





@dataclass

class PipelineState:

    session_id: str = ""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    software: SoftwareTarget = "relion"

    current_cp_id: str = "cp_01"

    current_cp_name: str = ""

    session_started: bool = False

    checkpoint_records: Dict[str, CheckpointRecord] = field(default_factory=dict)

    completed: List[str] = field(default_factory=list)

    failed: List[str] = field(default_factory=list)

    skipped: List[str] = field(default_factory=list)

    messages: List[Message] = field(default_factory=list)

    pending_images: List[Dict[str, Any]] = field(default_factory=list)

    image_observations: List[Dict[str, Any]] = field(default_factory=list)
    session_summary: str = ""
    last_qa_trace: Dict[str, Any] = field(default_factory=dict)
    user_input: str = ""
    user_input_lower: str = ""
    agent_reply: str = ""
    action_tag: ActionTag = "general"
    params: Dict[str, Any] = field(default_factory=dict)
    last_qc_result: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=dict)
    fault_diagnosis_state: Dict[str, Any] = field(default_factory=dict)
    next_node: str = "navigator"
    requires_human_approval: bool = False

    in_fault_mode: bool = False

    error: Optional[str] = None

    error_node: Optional[str] = None
    smart_qa_cards: Dict[str, Any] = field(default_factory=dict)
    response_profile: ResponseProfile = "teaching"



    def touch(self) -> None:

        self.last_updated = datetime.now().isoformat()



    def add_message(self, role: str, content: str, action_tag: ActionTag = "general", metadata: Optional[Dict[str, Any]] = None, image_refs: Optional[List[Dict[str, Any]]] = None) -> None:

        self.messages.append(Message(role=role, content=content, action_tag=action_tag, metadata=metadata or {}, image_refs=image_refs or []))

        self.touch()



    def mark_checkpoint(self, cp_id: str, status: CheckpointStatus, qc_summary: str = "", notes: str = "") -> None:

        rec = self.checkpoint_records.get(cp_id)

        if rec is None:

            rec = CheckpointRecord(cp_id=cp_id, cp_name_cn=self.current_cp_name)

            self.checkpoint_records[cp_id] = rec

        rec.status = status

        rec.qc_summary = qc_summary

        rec.notes = notes

        rec.qc_passed = status == "passed"

        if status == "passed" and cp_id not in self.completed:

            self.completed.append(cp_id)

            rec.completed_at = datetime.now().isoformat()

        elif status == "failed" and cp_id not in self.failed:

            self.failed.append(cp_id)

        elif status == "skipped" and cp_id not in self.skipped:

            self.skipped.append(cp_id)

        self.touch()



    def to_summary_dict(self) -> Dict[str, Any]:

        return {

            "session_id": self.session_id,

            "software": self.software,

            "current_cp_id": self.current_cp_id,

            "completed": self.completed,

            "failed": self.failed,

            "skipped": self.skipped,

            "params": self.params,

            "message_count": len(self.messages),

            "pending_images_count": len(self.pending_images),

            "image_observations_count": len(self.image_observations),
            "session_summary": self.session_summary,
            "last_updated": self.last_updated,
        }

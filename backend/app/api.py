from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .schema import PrescriptionRequest, PrescriptionResponse, PoseCorrectionRequest, PoseCorrectionResponse

router = APIRouter()


@router.post("/generate_prescription", response_model=PrescriptionResponse)
def generate_prescription(req: PrescriptionRequest):
    # Placeholder: in real project, call knowledge base + LLM here
    if not req.symptoms:
        raise HTTPException(status_code=400, detail="symptoms required")
    prescription = {
        "summary": f"基于主诉 {req.symptoms} 的初步康复处方（示例）",
        "actions": [
            {"name": "颈部侧屈拉伸", "sets": 3, "reps": 10, "note": "温和进行，出现强烈疼痛停止"}
        ]
    }
    return PrescriptionResponse(**prescription)


@router.post("/correct_pose", response_model=PoseCorrectionResponse)
def correct_pose(req: PoseCorrectionRequest):
    # Placeholder: in real project, run pose estimation and compare to template
    feedback = ["请收下巴，头部前屈过多。", "膝盖角度合适，继续保持。"]
    return PoseCorrectionResponse(feedback=feedback)

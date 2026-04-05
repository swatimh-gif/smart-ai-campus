from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Smart Campus AI Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory demo state
crowd_counts: Dict[str, int] = {
    "Library A": 24,
    "Library B": 46,
    "Study Hall": 18,
}
student_locations: Dict[str, str] = {}

location_distance_score: Dict[str, Dict[str, int]] = {
    "Block A": {"Library A": 2, "Library B": 6, "Study Hall": 4},
    "Block B": {"Library A": 5, "Library B": 2, "Study Hall": 3},
    "Hostel": {"Library A": 7, "Library B": 5, "Study Hall": 2},
    "Cafeteria": {"Library A": 4, "Library B": 4, "Study Hall": 3},
}

notes_db: List[Dict] = [
    {
        "id": 1,
        "subject": "Data Structures",
        "link": "https://example.com/ds-notes.pdf",
        "category": "CS Core",
        "summary": "Covers arrays, linked lists, trees, and graph basics.",
    },
    {
        "id": 2,
        "subject": "Machine Learning",
        "link": "https://example.com/ml-intro.ppt",
        "category": "AI",
        "summary": "Overview of supervised learning and model evaluation.",
    },
    {
        "id": 3,
        "subject": "Engineering Mathematics",
        "link": "https://example.com/em-unit2.pdf",
        "category": "Mathematics",
        "summary": "Linear algebra and differential equations quick revision.",
    },
]

print_queue: List[Dict] = []


class ScanRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    location: str = Field(default="Library A")


class AttendanceRequest(BaseModel):
    classes_attended: int = Field(..., ge=0)
    total_classes: int = Field(..., ge=1)


class NavigateRequest(BaseModel):
    destination: str = Field(..., min_length=1)
    from_location: str = Field(default="Block A")


class NoteUploadRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    link: str = Field(..., min_length=1)
    category: str = Field(default="General")


class PrintRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    document_link: str = Field(..., min_length=1)
    printer_location: str = Field(..., min_length=1)


def get_crowd_level(count: int) -> str:
    if count < 30:
        return "Low"
    if count <= 70:
        return "Medium"
    return "High"


@app.get("/")
def root():
    return {"message": "Smart Campus AI Platform API is running"}


@app.post("/scan-entry")
def scan_entry(payload: ScanRequest):
    location = payload.location
    if location not in crowd_counts:
        crowd_counts[location] = 0

    previous_location = student_locations.get(payload.student_id)
    if previous_location and previous_location != location:
        crowd_counts[previous_location] = max(0, crowd_counts[previous_location] - 1)

    if previous_location != location:
        crowd_counts[location] += 1

    student_locations[payload.student_id] = location

    return {
        "message": f"Student {payload.student_id} entered {location}",
        "location": location,
        "count": crowd_counts[location],
        "crowd_level": get_crowd_level(crowd_counts[location]),
    }


@app.post("/scan-exit")
def scan_exit(payload: ScanRequest):
    location = student_locations.get(payload.student_id, payload.location)
    if location not in crowd_counts:
        crowd_counts[location] = 0

    if student_locations.get(payload.student_id) == location:
        crowd_counts[location] = max(0, crowd_counts[location] - 1)
        student_locations.pop(payload.student_id, None)

    return {
        "message": f"Student {payload.student_id} exited {location}",
        "location": location,
        "count": crowd_counts[location],
        "crowd_level": get_crowd_level(crowd_counts[location]),
    }


@app.get("/crowd-status")
def crowd_status():
    locations = [
        {
            "location": name,
            "count": count,
            "crowd_level": get_crowd_level(count),
        }
        for name, count in crowd_counts.items()
    ]
    total_students = sum(crowd_counts.values())

    return {
        "locations": locations,
        "total_students": total_students,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/attendance")
def attendance(payload: AttendanceRequest):
    attended = payload.classes_attended
    total = payload.total_classes
    percentage = round((attended / total) * 100, 2)

    needed_classes = 0
    if percentage < 75:
        # Find smallest x such that (attended + x)/(total + x) >= 0.75
        x = 0
        while ((attended + x) / (total + x)) < 0.75:
            x += 1
        needed_classes = x

    message = (
        "Warning: Your attendance is below 75%."
        if percentage < 75
        else "Safe zone: Your attendance is above 75%."
    )

    return {
        "attendance_percentage": percentage,
        "classes_needed_for_75": needed_classes,
        "message": message,
    }


@app.post("/navigate")
def navigate(payload: NavigateRequest):
    destination = payload.destination
    from_location = payload.from_location

    # If the user requests generic library destination, suggest best one.
    if destination.lower() in {"library", "best library", "library nearest"}:
        distance_map = location_distance_score.get(from_location, {})

        def ranking_score(lib_name: str) -> int:
            crowd_penalty = crowd_counts.get(lib_name, 0)
            distance_penalty = distance_map.get(lib_name, 10)
            return crowd_penalty + (distance_penalty * 3)

        candidates = [name for name in crowd_counts.keys()]
        best = min(candidates, key=ranking_score)
        destination = best

    distance_map = location_distance_score.get(from_location, {})
    distance = distance_map.get(destination, 5)
    crowd = crowd_counts.get(destination, 0)
    crowd_level = get_crowd_level(crowd)

    instructions = [
        f"Start from {from_location}",
        "Follow main corridor for 100 meters",
        "Take the marked campus pathway",
        f"Reach {destination}",
    ]

    recommendation = (
        f"{destination} is currently {crowd_level} crowd with approx {crowd} students."
    )

    return {
        "destination": destination,
        "estimated_distance_score": distance,
        "crowd_level": crowd_level,
        "instructions": instructions,
        "recommendation": recommendation,
    }


@app.post("/upload-note")
def upload_note(payload: NoteUploadRequest):
    next_id = max([n["id"] for n in notes_db], default=0) + 1
    summary = f"Auto summary: Key points for {payload.subject}."
    note = {
        "id": next_id,
        "subject": payload.subject,
        "link": payload.link,
        "category": payload.category,
        "summary": summary,
    }
    notes_db.append(note)
    return {"message": "Note uploaded successfully", "note": note}


@app.get("/notes")
def get_notes(search: str = "", category: str = ""):
    filtered = notes_db

    if search:
        filtered = [
            note
            for note in filtered
            if search.lower() in note["subject"].lower()
            or search.lower() in note["summary"].lower()
        ]

    if category:
        filtered = [
            note for note in filtered if note["category"].lower() == category.lower()
        ]

    return {"notes": filtered, "count": len(filtered)}


@app.post("/print-request")
def print_request(payload: PrintRequest):
    ticket = {
        "request_id": len(print_queue) + 1,
        "student_id": payload.student_id,
        "document_link": payload.document_link,
        "printer_location": payload.printer_location,
        "status": "Queued",
        "queued_at": datetime.utcnow().isoformat() + "Z",
        "queue_position": len(print_queue) + 1,
    }
    print_queue.append(ticket)

    return {
        "message": "Print request queued successfully",
        "ticket": ticket,
        "queue_length": len(print_queue),
    }

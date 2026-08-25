from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.gender import infer_gender_from_full_name
from conftest import MockSheetWrapper, make_test_settings


def test_infer_gender_irina_smirnova():
    assert infer_gender_from_full_name("Ирина Смирнова") == "female"
    assert infer_gender_from_full_name("Смирнова Ирина") == "female"
    assert infer_gender_from_full_name("ирина смирнова") == "female"


def test_infer_gender_uses_surname_when_first_name_unknown():
    assert infer_gender_from_full_name("Алёна Кузнецова") == "female"
    assert infer_gender_from_full_name("Павел Смирнов") == "male"


def test_infer_gender_male_a_exceptions():
    assert infer_gender_from_full_name("Никита Козлов") == "male"
    assert infer_gender_from_full_name("Илья Петров") == "male"


def test_infer_gender_leaves_latin_demo_names_alone():
    assert infer_gender_from_full_name("Client One") is None


def test_booking_list_infers_female_for_irina_without_wetsuit():
    mock_sheet = MockSheetWrapper()
    mock_sheet.tabs["bookings"].append(
        {
            "booking_id": "bkg_irina",
            "club_id": "ice_beach_ruza",
            "client_id": "client_2",
            "date": "2026-06-01",
            "time": "10:30",
            "boat_id": "boat_1",
            "status": "confirmed",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": "2026-06-01T07:05:00Z",
            "updated_at": "2026-06-01T07:05:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "surf",
            "wetsuit_required": "false",
            "wetsuit_size": "",
            "wetsuit_gender": "",
            "notes": "",
            "discount": "0",
        }
    )
    app.dependency_overrides[get_sheet_wrapper] = lambda: mock_sheet
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    request_code = client.post("/auth/request-code", json={"staff_user_id": "staff_001", "phone": "+79990000001"})
    assert request_code.status_code == 200
    verify = client.post(
        "/auth/verify-code",
        json={"staff_user_id": "staff_001", "code": request_code.json()["debug_code"]},
    )
    assert verify.status_code == 200

    listed = client.get("/bookings?date=2026-06-01").json()
    irina = next(item for item in listed if item["client_id"] == "client_2")
    assert irina["client_name"] == "Ирина Смирнова"
    assert irina["wetsuit_gender"] == "female"
    app.dependency_overrides.clear()


def test_infer_gender_irina_smirnova():
    assert infer_gender_from_full_name("Ирина Смирнова") == "female"
    assert infer_gender_from_full_name("Смирнова Ирина") == "female"
    assert infer_gender_from_full_name("ирина смирнова") == "female"


def test_infer_gender_uses_surname_when_first_name_unknown():
    assert infer_gender_from_full_name("Алёна Кузнецова") == "female"
    assert infer_gender_from_full_name("Павел Смирнов") == "male"


def test_infer_gender_male_a_exceptions():
    assert infer_gender_from_full_name("Никита Козлов") == "male"
    assert infer_gender_from_full_name("Илья Петров") == "male"


def test_infer_gender_leaves_latin_demo_names_alone():
    assert infer_gender_from_full_name("Client One") is None

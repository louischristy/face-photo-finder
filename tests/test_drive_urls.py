import pytest

from app.services.drive_urls import extract_folder_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://drive.google.com/drive/folders/1NV0Eu1KQCTACiXgEwEnVFdffaqTgi9LH?usp=drive_link", "1NV0Eu1KQCTACiXgEwEnVFdffaqTgi9LH"),
        ("https://drive.google.com/drive/folders/1-nOE7Adm5ohEDfS9y2Gbl6EUMeVC2_VX?usp=drive_link", "1-nOE7Adm5ohEDfS9y2Gbl6EUMeVC2_VX"),
        ("https://drive.google.com/drive/folders/1O9AQG-wWCrEquQ0MAcmx_QqSpFu9Q02E?usp=drive_link", "1O9AQG-wWCrEquQ0MAcmx_QqSpFu9Q02E"),
    ],
)
def test_extract_folder_id(value: str, expected: str):
    assert extract_folder_id(value) == expected

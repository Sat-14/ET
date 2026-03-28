from src.models.user import City, IndividualProfile
from src.parsers.form16_parser import merge_form16_into_profile


def test_merge_form16_into_profile_overrides_tax_fields_only():
    base_profile = IndividualProfile(name="Asha", city=City.NON_METRO, other_income=120000)
    parsed_data = {
        "gross_salary": 1_200_000,
        "exemptions": {
            "hra": 240_000,
            "lta": 20_000,
        },
        "deductions": {
            "80CCD_1B": 50_000,
            "80D": 25_000,
            "24b": 150_000,
        },
    }

    merged = merge_form16_into_profile(parsed_data, base_profile=base_profile)

    assert merged.name == "Asha"
    assert merged.city == City.NON_METRO
    assert merged.other_income == 120000
    assert merged.salary.hra == 240_000
    assert merged.salary.basic == 480_000
    assert merged.deductions.nps_additional == 50_000
    assert merged.deductions.self_health_insurance == 25_000
    assert merged.deductions.home_loan_interest == 150_000

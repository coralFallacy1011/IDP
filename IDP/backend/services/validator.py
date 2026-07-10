def validate(doc_type, data):
    required = {
        "rental_agreement": ["landlord_name", "tenant_name", "rent"],
        "affidavit": ["name", "purpose"],
        "affidavit_general": ["name", "purpose"],
        "fir": ["complainant_name", "incident_details"],
        "employment_contract": ["employee_name", "salary"],
        "legal_notice": ["sender_name", "recipient_name"],
        "power_of_attorney": ["grantor_name", "grantee_name"],
    }

    # If doc_type is unknown, skip field validation
    if doc_type not in required:
        return True, "ok"

    for field in required[doc_type]:
        if not data.get(field):
            return False, f"{field} is required"

    return True, "ok"
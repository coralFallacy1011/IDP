from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))

def generate_document(doc_type, data):
    mapping = {
        "rental_agreement": "rental_agreement.j2",
        "affidavit_general": "affidavit_general.j2",
        "legal_notice": "legal_notice.j2",
        "employment_contract": "employment_contract.j2",
        "power_of_attorney": "power_of_attorney.j2"
    }

    template = env.get_template(mapping[doc_type])
    return template.render(**data)
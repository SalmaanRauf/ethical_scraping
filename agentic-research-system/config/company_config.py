"""
Company configuration and canonicalization mapping.
"""

COMPANY_SLUGS = {
    # Canonical mappings
    "capital one": "Capital_One",
    "capitalone": "Capital_One",
    "Capital one": "Capital_One",
    "cof": "Capital_One",
    "capital one financial": "Capital_One",
    "capital one financial corp": "Capital_One",
    
    "fannie mae": "Fannie_Mae",
    "fnma": "Fannie_Mae",
    "federal national mortgage association": "Fannie_Mae",
    
    "freddie mac": "Freddie_Mac",
    "fmcc": "Freddie_Mac",
    "federal home loan mortgage corporation": "Freddie_Mac",
    
    "navy federal": "Navy_Federal_Credit_Union",
    "navy federal credit union": "Navy_Federal_Credit_Union",
    
    "penfed": "PenFed_Credit_Union",
    "penfed credit union": "PenFed_Credit_Union",
    
    "eaglebank": "Eagle_Bank",
    "eagle bank": "Eagle_Bank",
    "egbn": "Eagle_Bank",
    
    "capital bank": "Capital_Bank_N.A.",
    "capital bank n.a.": "Capital_Bank_N.A.",
    "cbnk": "Capital_Bank_N.A."
}

COMPANY_DISPLAY_NAMES = {
    "Capital_One": "Capital One Financial Corporation",
    "Fannie_Mae": "Federal National Mortgage Association",
    "Freddie_Mac": "Federal Home Loan Mortgage Corporation",
    "Navy_Federal_Credit_Union": "Navy Federal Credit Union",
    "PenFed_Credit_Union": "PenFed Credit Union",
    "Eagle_Bank": "EagleBank",
    "Capital_Bank_N.A.": "Capital Bank N.A."
}

def get_available_companies():
    """Return list of available companies for user reference."""
    return list(COMPANY_DISPLAY_NAMES.values())

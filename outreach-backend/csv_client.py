import csv

def get_contacts_from_csv(path: str = "contacts.csv", limit: int = 10):
    contacts = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            contacts.append(row)
            if len(contacts) >= limit:
                break
    return contacts

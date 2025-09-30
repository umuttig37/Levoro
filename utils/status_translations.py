"""
Status Translation Utilities
Centralized status translations for orders
"""

# Status translations (English to Finnish)
STATUS_TRANSLATIONS = {
    'NEW': 'UUSI',
    'CONFIRMED': 'TEHTÄVÄ_VAHVISTETTU',
    'ASSIGNED_TO_DRIVER': 'MÄÄRITETTY_KULJETTAJALLE',
    'DRIVER_ARRIVED': 'KULJETTAJA_SAAPUNUT',
    'PICKUP_IMAGES_ADDED': 'NOUTOKUVAT_LISÄTTY',
    'IN_TRANSIT': 'TOIMITUKSESSA',
    'DELIVERY_ARRIVED': 'KULJETUS_SAAPUNUT',
    'DELIVERY_IMAGES_ADDED': 'TOIMITUSKUVAT_LISÄTTY',
    'DELIVERED': 'TOIMITETTU',
    'CANCELLED': 'PERUUTETTU'
}

# User-friendly status descriptions
STATUS_DESCRIPTIONS = {
    'NEW': 'Tilaus vastaanotettu ja odottaa vahvistusta',
    'CONFIRMED': 'Tilaus vahvistettu! Kuljettaja määritetään pian',
    'ASSIGNED_TO_DRIVER': 'Kuljettaja määritetty ja matkalla noutopaikalle',
    'DRIVER_ARRIVED': 'Kuljettaja saapunut noutopaikalle ja aloittaa ajoneuvon tarkastuksen',
    'PICKUP_IMAGES_ADDED': 'Ajoneuvon tila dokumentoitu - kuljetus alkaa pian',
    'IN_TRANSIT': 'Ajoneuvonne on nyt matkalla määränpäähän',
    'DELIVERY_ARRIVED': 'Ajoneuvonne on saapunut toimituspaikalle',
    'DELIVERY_IMAGES_ADDED': 'Toimitus dokumentoitu - ajoneuvonne on valmis luovutettavaksi',
    'DELIVERED': 'Kuljetus suoritettu onnistuneesti! Kiitos Levoro-palvelun käytöstä',
    'CANCELLED': 'Tilaus on peruutettu'
}


def translate_status(status: str) -> str:
    """Translate English status to Finnish"""
    return STATUS_TRANSLATIONS.get(status, status)


def get_status_description(status: str) -> str:
    """Get user-friendly status description"""
    return STATUS_DESCRIPTIONS.get(status, 'Tuntematon tila')
"""
Status Translation Utilities
Centralized status translations for orders
"""

# Status translations (English to Finnish) - Friendly text for emails
STATUS_TRANSLATIONS = {
    'NEW': 'Uusi tilaus',
    'CONFIRMED': 'Tilaus vahvistettu',
    'ASSIGNED_TO_DRIVER': 'Noudossa',
    'DRIVER_ARRIVED': 'Kuljettaja saapunut',
    'PICKUP_IMAGES_ADDED': 'Noutokuvat lisätty',
    'IN_TRANSIT': 'Kuljetuksessa',
    'DELIVERY_ARRIVED': 'Toimitus saapunut',
    'DELIVERY_IMAGES_ADDED': 'Toimituskuvat lisätty',
    'DELIVERED': 'Toimitettu',
    'CANCELLED': 'Peruutettu'
}

# User-friendly status descriptions
STATUS_DESCRIPTIONS = {
    'NEW': 'Tilaus vastaanotettu ja odottaa vahvistusta',
    'CONFIRMED': 'Tilaus vahvistettu! Kuljettaja määritetään pian',
    'ASSIGNED_TO_DRIVER': 'Ajoneuvosi haetaan pian - kuljettaja on matkalla noutopaikalle',
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
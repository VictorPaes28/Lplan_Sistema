from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from workflow_aprovacao.services.geocoding import (
    enrich_geolocation,
    google_maps_url,
    reverse_geocode,
)


class GeocodingTests(SimpleTestCase):
    def test_google_maps_url(self):
        url = google_maps_url(latitude=-8.084836, longitude=-34.896197)
        self.assertEqual(url, 'https://www.google.com/maps?q=-8.084836,-34.896197')

    @patch('workflow_aprovacao.services.geocoding.urllib.request.urlopen')
    def test_reverse_geocode_returns_address(self, mock_urlopen):
        payload = {
            'display_name': 'Rua Teste, Recife, PE',
            'address': {
                'road': 'Rua da Aurora',
                'house_number': '100',
                'suburb': 'Boa Vista',
                'city': 'Recife',
                'state': 'Pernambuco',
            },
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = __import__('json').dumps(payload).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = reverse_geocode(latitude=-8.084836, longitude=-34.896197)
        self.assertIn('Rua da Aurora', result['address'])
        self.assertIn('google.com/maps', result['maps_url'])

    @patch('workflow_aprovacao.services.geocoding.reverse_geocode')
    def test_enrich_geolocation_fills_address(self, mock_reverse):
        mock_reverse.return_value = {
            'address': 'Rua da Aurora, Boa Vista, Recife, Pernambuco',
            'maps_url': 'https://www.google.com/maps?q=-8.084836,-34.896197',
        }
        geo = {'latitude': -8.084836, 'longitude': -34.896197, 'accuracy_m': 85}
        enriched = enrich_geolocation(geo)
        self.assertEqual(enriched['address'], mock_reverse.return_value['address'])
        self.assertIn('google.com/maps', enriched['maps_url'])

    def test_enrich_geolocation_skips_when_address_exists(self):
        geo = {
            'latitude': -8.084836,
            'longitude': -34.896197,
            'address': 'Endereço já informado',
        }
        enriched = enrich_geolocation(dict(geo))
        self.assertEqual(enriched['address'], 'Endereço já informado')

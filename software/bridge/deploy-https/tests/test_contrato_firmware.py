"""Contrato compartilhado do endpoint publico e exemplo do firmware."""
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[4]

class ContratoFirmware(unittest.TestCase):
    def test_firmware_omite_flag_mas_nao_libera_http(self):
        source = (ROOT / 'firmware/mascote/mascote.ino').read_text()
        self.assertRegex(source, r'#ifndef PONTE_HTTPS_OBRIGATORIO\s+#define PONTE_HTTPS_OBRIGATORIO 1')

    def test_exemplo_aponta_https_443_publico(self):
        config = (ROOT / 'firmware/mascote/config.exemplo.h').read_text()
        url = re.search(r'#define\s+PONTE_URL\s+"([^"]+)"', config).group(1)
        parsed = urlsplit(url)
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.hostname, '179.198.122.200')
        self.assertEqual(parsed.port or 443, 443)
        self.assertRegex(config, r'#define\s+PONTE_HTTPS_OBRIGATORIO\s+1')

if __name__ == '__main__':
    unittest.main()

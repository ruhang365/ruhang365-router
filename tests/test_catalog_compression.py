import gzip
import io
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ruhang365-router/scripts'
sys.path.insert(0, str(SCRIPTS))
import community_catalog


class Response(io.BytesIO):
    def __init__(self, body, encoding='gzip'):
        super().__init__(body)
        self.headers = {'Content-Encoding': encoding}


class CompressedCatalogTests(unittest.TestCase):
    def test_compressed_catalog_uses_identical_validation_and_digest(self):
        catalog = community_catalog.load_catalog()
        raw = json.dumps(catalog).encode()
        result = community_catalog.resolve_catalog(
            'https://rhzl.ruhang365.cn',
            opener=lambda request, timeout: Response(gzip.compress(raw)),
        )
        self.assertEqual(result['source'], 'online')
        self.assertEqual(result['catalog'], catalog)

    def test_invalid_gzip_falls_back_without_destroying_snapshot(self):
        result = community_catalog.resolve_catalog(
            'https://rhzl.ruhang365.cn',
            opener=lambda request, timeout: Response(b'not gzip'),
        )
        self.assertEqual(result['source'], 'offline_fallback')
        self.assertEqual(result['catalog'], community_catalog.load_catalog())

    def test_decompression_is_bounded(self):
        raw = gzip.compress(b'x' * (community_catalog.MAX_CATALOG_BYTES + 1))
        with self.assertRaises(ValueError):
            community_catalog._read_catalog_response(Response(raw))

    def test_truncated_gzip_falls_back(self):
        raw = gzip.compress(b'{}')[:-4]
        result = community_catalog.resolve_catalog(
            'https://rhzl.ruhang365.cn',
            opener=lambda request, timeout: Response(raw),
        )
        self.assertEqual(result['source'], 'offline_fallback')


if __name__ == '__main__':
    unittest.main()

"""Integridad binaria y coincidencias locales; no certifica originalidad académica."""
from hashlib import sha256
from pathlib import Path
import re
import unicodedata


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class LocalSimilarityIndex:
    def __init__(self):
        self.documents = []

    def compare_and_add(self, source: str, text: str) -> dict:
        words = re.findall(r'[^\W_]+', unicodedata.normalize('NFC', text).casefold())
        base = {'algorithm': 'jaccard_word_5grams', 'threshold': 0.8,
                'minimum_words': 30, 'matches': [], 'references_compared': 0}
        if len(words) < 30:
            return {**base, 'status': 'texto_insuficiente'}
        shingles = {' '.join(words[i:i + 5]) for i in range(len(words) - 4)}
        matches = []
        for previous_source, previous in self.documents:
            common = shingles & previous
            score = len(common) / len(shingles | previous)
            if score >= 0.8:
                matches.append({'source': previous_source, 'score': round(score, 6),
                                'shared_fragments': sorted(common)[:3]})
        count = len(self.documents)
        self.documents.append((source, shingles))
        status = ('coincidencias_detectadas' if matches else
                  'sin_coincidencias_sobre_umbral' if count else 'sin_referencias_previas')
        return {**base, 'status': status, 'references_compared': count, 'matches': matches}

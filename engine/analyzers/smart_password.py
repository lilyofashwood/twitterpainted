"""Smart password wordlist generator using context from filename and metadata."""

from pathlib import Path
from typing import List, Set, Dict, Any
import re
from datetime import datetime


def generate_smart_wordlist(
    filename: str,
    metadata: Dict[str, Any],
    max_words: int = 500
) -> List[str]:
    """Generate context-aware password candidates from image metadata and filename."""
    candidates: Set[str] = set()

    # 1. From filename
    candidates.update(_extract_from_filename(filename))

    # 2. From EXIF metadata
    candidates.update(_extract_from_metadata(metadata))

    # 3. Common patterns
    candidates.update(_generate_common_patterns())

    # 4. Mutations
    base_words = list(candidates)
    candidates.update(_generate_mutations(base_words))

    # Convert to sorted list (shorter passwords first, then alphabetical)
    wordlist = sorted(list(candidates), key=lambda x: (len(x), x))

    return wordlist[:max_words]


def _extract_from_filename(filename: str) -> Set[str]:
    """Extract password candidates from filename."""
    candidates: Set[str] = set()

    # Remove extension
    name = Path(filename).stem

    # Add full name (lowercase)
    candidates.add(name.lower())

    # Split by common separators
    parts = re.split(r'[_\-\s.]+', name)
    for part in parts:
        if part and len(part) >= 3:
            candidates.add(part.lower())
            candidates.add(part.capitalize())
            candidates.add(part.upper())

    # Extract numbers
    numbers = re.findall(r'\d+', name)
    for num in numbers:
        candidates.add(num)

    # Extract dates (YYYY-MM-DD, YYYYMMDD, etc.)
    date_patterns = [
        r'\d{4}[-_]?\d{2}[-_]?\d{2}',  # 2024-01-15 or 20240115
        r'\d{2}[-_]?\d{2}[-_]?\d{4}',  # 01-15-2024
    ]

    for pattern in date_patterns:
        dates = re.findall(pattern, name)
        for date in dates:
            cleaned = date.replace('-', '').replace('_', '')
            candidates.add(cleaned)

    return candidates


def _extract_from_metadata(metadata: Dict[str, Any]) -> Set[str]:
    """Extract password candidates from EXIF metadata."""
    candidates: Set[str] = set()

    # Common EXIF fields to check
    fields_to_check = [
        "Author", "Artist", "Creator", "Copyright", "Software",
        "DateTime", "DateTimeOriginal", "DateTimeDigitized",
        "Make", "Model", "Comment", "UserComment", "ImageDescription"
    ]

    for field in fields_to_check:
        value = metadata.get(field, "")
        if not value or not isinstance(value, str):
            continue

        # Clean value
        value = value.strip()

        if len(value) >= 3 and len(value) <= 50:
            candidates.add(value.lower())
            candidates.add(value.replace(" ", ""))

            # Extract words
            words = re.split(r'[_\-\s.]+', value)
            for word in words:
                if len(word) >= 3:
                    candidates.add(word.lower())

    # Extract dates from DateTime fields
    datetime_fields = ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]
    for field in datetime_fields:
        dt_str = metadata.get(field, "")
        if dt_str:
            # Try to parse date
            candidates.update(_parse_datetime(dt_str))

    # GPS coordinates → location-based passwords
    gps = _extract_gps(metadata)
    if gps:
        candidates.add(gps)

    return candidates


def _parse_datetime(dt_str: str) -> Set[str]:
    """Parse datetime string and generate password candidates."""
    candidates: Set[str] = set()

    # EXIF format: "2024:01:15 14:30:22"
    patterns = [
        (r'(\d{4}):(\d{2}):(\d{2})', '{0}{1}{2}'),  # 20240115
        (r'(\d{4})-(\d{2})-(\d{2})', '{0}{1}{2}'),  # 2024-01-15
        (r'(\d{2})/(\d{2})/(\d{4})', '{2}{0}{1}'),  # 01/15/2024
    ]

    for pattern, fmt in patterns:
        match = re.search(pattern, dt_str)
        if match:
            date_str = fmt.format(*match.groups())
            candidates.add(date_str)

            # Add year only
            if match.group(1):
                candidates.add(match.group(1))

    return candidates


def _extract_gps(metadata: Dict[str, Any]) -> str:
    """Extract GPS coordinates if present."""
    # This is a placeholder - full implementation would parse GPS data
    if "GPSInfo" in metadata or "GPS" in str(metadata):
        return "gps"
    return ""


def _generate_common_patterns() -> Set[str]:
    """Generate common password patterns."""
    common = {
        # Common CTF passwords
        "password", "flag", "secret", "hidden", "steg", "steganography",
        "ctf", "challenge", "key", "admin", "root",

        # Years
        "2024", "2023", "2022", "2021",

        # Simple patterns
        "123", "1234", "12345", "123456",
        "abc", "test", "demo",
    }

    return common


def _generate_mutations(base_words: List[str]) -> Set[str]:
    """Generate mutations of base words."""
    mutations: Set[str] = set()

    for word in base_words[:50]:  # Limit to prevent explosion
        if not word or len(word) > 20:
            continue

        # Capitalization
        mutations.add(word.capitalize())
        mutations.add(word.upper())
        mutations.add(word.lower())

        # Append numbers
        for suffix in ["1", "123", "2024", "!"]:
            mutations.add(word + suffix)

        # Prepend numbers
        for prefix in ["1", "2024"]:
            mutations.add(prefix + word)

        # Leetspeak (simple)
        leet = _to_leetspeak(word)
        if leet != word:
            mutations.add(leet)

        # Reverse
        mutations.add(word[::-1])

        # First letter caps + numbers
        if len(word) > 2:
            mutations.add(word[0].upper() + word[1:] + "123")

    return mutations


def _to_leetspeak(word: str) -> str:
    """Convert word to simple leetspeak."""
    leet_map = {
        'a': '4', 'e': '3', 'i': '1', 'o': '0',
        's': '5', 't': '7', 'l': '1', 'g': '9'
    }

    result = []
    for char in word.lower():
        result.append(leet_map.get(char, char))

    return ''.join(result)


def generate_wordlist_for_steghide(
    filename: str,
    metadata: Dict[str, Any],
    output_path: Path
) -> int:
    """Generate wordlist file for steghide/stegseek."""
    wordlist = generate_smart_wordlist(filename, metadata, max_words=1000)

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        for word in wordlist:
            f.write(word + '\n')

    return len(wordlist)

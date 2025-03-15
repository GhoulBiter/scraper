"""
Text encoding detection and conversion utilities
"""

import re
from urllib.parse import urlparse, quote

import aiohttp
from loguru import logger


class EncodingHandler:
    """Handles text encoding detection and conversion."""

    # Common fallback encodings to try
    FALLBACK_ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

    @staticmethod
    def detect_encoding_from_headers(headers):
        """Detect encoding from HTTP headers."""
        content_type = headers.get("content-type", "")
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].strip()
            # Clean up encoding name
            if ";" in encoding:
                encoding = encoding.split(";")[0]
            if encoding.startswith('"') and encoding.endswith('"'):
                encoding = encoding[1:-1]
            return encoding
        return None

    @staticmethod
    def detect_encoding_from_html(html_bytes):
        """Detect encoding from HTML meta tags."""
        # Try to decode as ASCII first to find meta tags
        try:
            html_start = html_bytes[:4096].decode("ascii", errors="ignore")
            # Check for meta charset
            meta_match = re.search(
                r'<meta[^>]+charset=["\'](.*?)["\']', html_start, re.IGNORECASE
            )
            if meta_match:
                return meta_match.group(1)

            # Check for XML declaration
            xml_match = re.search(
                r'<\?xml[^>]+encoding=["\'](.*?)["\']', html_start, re.IGNORECASE
            )
            if xml_match:
                return xml_match.group(1)

            # Check for content-type meta
            content_type_match = re.search(
                r'<meta[^>]+http-equiv=["\'](content-type)["\'][^>]+content=["\'](.*?)["\']',
                html_start,
                re.IGNORECASE,
            )
            if content_type_match and "charset=" in content_type_match.group(2).lower():
                charset = (
                    content_type_match.group(2).lower().split("charset=")[-1].strip()
                )
                if ";" in charset:
                    charset = charset.split(";")[0]
                return charset

        except Exception as e:
            logger.warning(f"Error detecting encoding from HTML: {e}")

        return None

    @staticmethod
    async def decode_html(response):
        """Decode HTML content with proper encoding detection."""
        # Get raw bytes
        html_bytes = await response.read()

        # Try from HTTP headers first
        encoding = EncodingHandler.detect_encoding_from_headers(response.headers)

        # If no encoding in headers, try from HTML content
        if not encoding:
            encoding = EncodingHandler.detect_encoding_from_html(html_bytes)

        # If encoding detected, try to decode
        if encoding:
            try:
                return html_bytes.decode(encoding, errors="replace")
            except (LookupError, UnicodeDecodeError) as e:
                logger.warning(
                    f"Failed to decode using detected encoding {encoding}: {e}"
                )

        # Try fallback encodings
        for enc in EncodingHandler.FALLBACK_ENCODINGS:
            try:
                return html_bytes.decode(enc, errors="replace")
            except (LookupError, UnicodeDecodeError):
                continue

        # Last resort: force decode with replace
        return html_bytes.decode("utf-8", errors="replace")

    @staticmethod
    def normalize_url(url):
        """Normalize URL for Unicode."""
        try:
            # Parse URL
            parsed = urlparse(url)

            # Normalize hostname using IDNA encoding
            hostname = parsed.netloc.encode("idna").decode("ascii")

            # Normalize path using percent-encoding
            path = quote(parsed.path, safe="/%")

            # Reconstruct URL
            normalized = parsed._replace(netloc=hostname, path=path)
            return normalized.geturl()

        except Exception as e:
            logger.warning(f"Error normalizing URL {url}: {e}")
            return url


class HTMLCleaner:
    """Helper class for cleaning and extracting content from HTML."""

    @staticmethod
    def clean_text(text):
        """Clean text by removing extra whitespace and normalizing."""
        if not text:
            return ""

        # Replace HTML entities
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @staticmethod
    def extract_meta_description(html):
        """Extract meta description from HTML."""
        if not html:
            return ""

        meta_desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
            html,
            re.IGNORECASE,
        )

        if meta_desc_match:
            return HTMLCleaner.clean_text(meta_desc_match.group(1))

        return ""

    @staticmethod
    def extract_text_from_html(html, max_length=1000):
        """Extract plain text from HTML by removing tags (simple version)."""
        if not html:
            return ""

        # Remove scripts and style sections
        html = re.sub(
            r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove comments
        html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)

        # Remove tags while keeping their content
        text = re.sub(r"<[^>]*>", " ", html)

        # Clean the text
        text = HTMLCleaner.clean_text(text)

        # Truncate if needed
        if max_length and len(text) > max_length:
            return text[:max_length] + "..."

        return text
